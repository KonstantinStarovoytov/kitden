# Part 2: The gateway's access contract — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person can trust what the Kitden gateway offers: a strict mode allows only chosen tools, new tools wait, a switched-off tool is refused at once, an unknown folder is said plainly, reads and writes are shown as a helper with one batch switch, and calls are counted.

**Architecture:** The rules file `gateway.json` keeps its shape and gains one field, `rules.global[<server>].mode`. `settings.py` learns strict mode and two small files (`is_allowed`, `count_call`); `views.py` adds hints and the new step builders; the proxy checks the rules again on every call; the page gets one switch, one word per tool and one batch button; `after.py` gets the review words. Every new file in the data folder reads as empty when broken.

**Tech Stack:** Python 3.13, the official MCP SDK 2.3 (server session notifications), Starlette; plain ES modules; pytest with the echo server fixture; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-21-review-follow-up-design.md`, Part 2 (2.1 to 2.7) and 1.5's token line. Master plan: `docs/superpowers/plans/2026-10-21-review-follow-up.md` (the names `GATEWAY_STRICT`, `GATEWAY_RULES`, `hint`, `hint_from`, `is_allowed`, `count_call` are fixed there).

## Global Constraints

- Code, comments, UI text and docs in simple English, short and plain (`AGENTS.md`).
- Every switch is a change through the engine: preview → Apply with a backup → verify → Undo. Only `gateway.json` changes through review; `gateway-tools.json` and `gateway-calls.json` are found data and are written directly.
- A secret never reaches the page, a review, an error result or stderr; hints and counts carry no arguments or results.
- `docs/design.md`: a switch flips only after `verified`; new text tested in `tests/unit/test_page_words.py`; page logic pure and tested with node.
- Tests use sandbox homes only; the gateway tests use `tests/fixtures/fake_mcp/echo_server.py`.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`.
- Commit messages: a short plain subject, no prefix.
- A fact about the MCP SDK or a client is checked against its docs with the date in a comment.
- No new runtime dependency.

## Review Focus

1. Today's `gateway.json` (no `mode` anywhere) reads exactly as before: same `allowed_tools`, same `state_in` (Task 1 test `test_settings_without_a_mode_read_as_before`).
2. Strict mode turned on for a server whose tool list is not known yet: the review writes the mode only and says the tools will show as off until turned on (Task 2 test `test_strict_on_without_a_tool_list_writes_the_mode_only`).
3. In strict mode a tool with an explicit `on` under a server that is `off`: still refused, the server decides first (Task 4 test `test_a_tool_on_under_a_server_off_is_refused`).
4. A tool name that holds a verb inside another word (`runway_status`, `settle_bill`, `posture`) is `unknown`, not `may write` (Task 6 test `test_verbs_match_whole_words_only`).
5. `gateway-calls.json` broken or unwritable: calls go through, counts read as none, nothing on stderr but one plain line (Task 7 test `test_a_broken_calls_file_does_not_stop_a_call`).

---

### Task 1: Strict mode in the rules (2.1)

**Files:**
- Modify: `src/kitden/local_gateway/settings.py:96-152` (`own_state`, `_is_on`, `_scopes`, `state_in`, `servers_on`, `allowed_tools`) and `154-167` (`rule_step`)
- Test: `tests/unit/test_local_gateway_settings.py`

**Interfaces:**
- Produces: `strict_mode(settings: dict, server: str) -> bool` (true when `rules.global[server].mode == "strict"`); `_is_on(scopes, server, tool, strict=False)`: with no state in any scope, a tool is on unless `strict`; a server without a state is on in both modes; `state_in`, `servers_on`, `allowed_tools` call it with `strict_mode(settings, server)`; `strict_step(home: Path, server: str, on: bool) -> Step` = `settings_step(home, ("rules", "global", server, "mode"), "strict" if on else ABSENT, server)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_in_strict_mode_a_tool_without_a_rule_is_off():
    settings = {"servers": {"github": {}}, "rules": {"global": {"github": {"mode": "strict", "tools": {"list_issues": "on"}}}, "projects": {}}}
    tools = {"github": [tool("list_issues"), tool("create_issue")]}
    assert [t["name"] for t in allowed_tools(settings, tools, [])["github"]] == ["list_issues"]
    assert state_in(settings, [], "github", "create_issue") == "off"
    assert state_in(settings, [], "github", None) == "on"  # the server itself needs no rule


def test_a_project_rule_still_wins_in_strict_mode():
    settings = {"servers": {"github": {}}, "rules": {"global": {"github": {"mode": "strict"}}, "projects": {"/p": {"github": {"tools": {"create_issue": "on"}}}}}}
    assert state_in(settings, ["/p"], "github", "create_issue") == "on"
    assert state_in(settings, [], "github", "create_issue") == "off"


def test_settings_without_a_mode_read_as_before():
    # SERVERS and the rules used by test_tools_follow_global_then_project_rules, unchanged
    ...
    assert allowed_tools(settings, tools, ["/p"]) == before  # the value that test asserts today


def test_strict_step_writes_and_removes_the_mode(tmp_path):
    step = strict_step(tmp_path, "github", True)
    assert step.edit.key == ("rules", "global", "github", "mode") and step.edit.after == "strict"
    assert strict_step(tmp_path, "github", False).edit.after is ABSENT
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_local_gateway_settings.py -v -k "strict or as_before"`
Expected: FAIL: `strict_step` and `strict_mode` do not exist; the first test gets both tools.

- [ ] **Step 3: Implement** the four functions in `settings.py` as the interface says. `own_state` stays; `mode` is read with `_dict(rules["global"].get(server)).get("mode") == "strict"`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_local_gateway_settings.py -v`
Expected: PASS, including every test that was there.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/local_gateway/settings.py tests/unit/test_local_gateway_settings.py
git commit -m "Gateway: strict mode in the rules"
```

---

### Task 2: The strict switch on the page (2.1)

**Files:**
- Modify: `src/kitden/changes/actions.py:389-391` (add `GATEWAY_STRICT = "gateway.strict"`), `605-660` (`_carried_rules` returns whether a Codex allowlist was carried), `706-800` (`local_move_steps` appends `strict_step` then)
- Modify: `src/kitden/local_gateway/views.py:101-116` (`tools_view` adds `"strict": bool`) and after `rule_steps` (new `strict_steps`)
- Modify: `src/kitden/web/app.py:835-837` (preview dispatch: `GATEWAY_STRICT`)
- Modify: `src/kitden/views/after.py` (new `_strict_words`, wired in `after_words`)
- Modify: `src/kitden/web/static/js/panel.js:420-470` (`toolsSection`: the switch above the list)
- Test: `tests/unit/test_local_gateway_views.py`, `tests/unit/test_api_changes.py`, `tests/unit/test_local_gateway_move.py`, `tests/unit/test_after.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `strict_steps(home: Path, params: dict, tools: dict[str, list[dict]]) -> list[Step]` with `params = {"server": str, "state": "on" | "off"}`: `on` gives `strict_step(home, server, True)` plus `rule_step(home, None, server, t["name"], "on")` for every tool in `allowed_tools(load_settings(home), tools, [])[server]` that has no own global `on`; `off` gives `strict_step(home, server, False)` only. Raises `ValueError("Choose a server in the Kitden gateway.")` / `ValueError("Choose on or off.")` like `rule_steps`. `tools_view(...)["strict"]` is `strict_mode(settings, server)`. Review words: on: `"Strict mode on for <server>: only tools you turned on are offered; a new tool waits until you turn it on. For a real guarantee, give <server> a token that can only read."`; off: `"Strict mode off for <server>: a tool without a rule is on."`; without a known tool list: `"Strict mode on for <server>: its tools show as off until you turn them on. For a real guarantee, give <server> a token that can only read."`. Page: the switch's accessible name is `"Strict: only tools you turned on"`, hover `"Set for all projects"` when a project is picked (disabled then).

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_local_gateway_views.py`:

```python
def test_strict_on_writes_the_mode_and_an_on_for_every_offered_tool(home):
    # gateway.json holds github with tools list_issues, create_issue cached; create_issue is off
    steps = strict_steps(home, {"server": "github", "state": "on"}, load_tools(home))
    assert [(s.edit.key[-1], s.edit.after) for s in steps] == [("mode", "strict"), ("list_issues", "on")]


def test_strict_on_without_a_tool_list_writes_the_mode_only(home):
    assert [s.edit.key[-1] for s in strict_steps(home, {"server": "notion", "state": "on"}, {})] == ["mode"]


def test_tools_view_says_strict(home):
    assert tools_view(settings_with_mode, load_tools(home), "github", [])["strict"] is True
```

`tests/unit/test_api_changes.py`: `test_gateway_strict_previews_applies_and_undoes(client, home)`: POST `/api/changes/preview` with `{"action": "gateway.strict", "targets": [], "params": {"server": "github", "state": "on"}}` → 200 and the after note contains `"Strict mode on for github"`; apply → `gateway.json` has the mode; undo → it is gone.

`tests/unit/test_local_gateway_move.py`: `test_a_codex_allowlist_turns_strict_on(home)`: a Codex entry with `enabled_tools = ["list_issues"]` moved in → a step with key `("rules", "global", "github", "mode")` and `"strict"`, and the carried `off` rules as today.

`tests/unit/test_after.py`: the three sentences above, one test each.

`test_page_words.py`: `panel.js` contains `"Strict: only tools you turned on"` and `"Set for all projects"`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_local_gateway_views.py tests/unit/test_api_changes.py tests/unit/test_local_gateway_move.py tests/unit/test_after.py tests/unit/test_page_words.py -v -k strict`
Expected: FAIL everywhere (`strict_steps`, the action, the words and the switch do not exist).

- [ ] **Step 3: Implement** the Python side (`strict_steps`, the action constant, the dispatch line after `GATEWAY_RULE`, `_carried_rules` returning a `(rules, strict)` pair and `local_move_steps` appending the step, `_strict_words` chosen in `after_words` by `change.action == GATEWAY_STRICT`).

- [ ] **Step 4: Implement the switch** in `toolsSection`: above the tool list, `switchNode(answer.strict, press)` with the accessible name; `press` calls `review({ action: "gateway.strict", targets: [], params: { server, state: answer.strict ? "off" : "on" } }, { back })` with the same `back` the tool switches use; when `state.project` is set, `node.disabled = true` and `node.title = "Set for all projects"`.

- [ ] **Step 5: Run the tests**

Run: the Step 2 command without `-k`, plus `node --test tests/frontend/*.test.mjs`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/kitden/changes/actions.py src/kitden/local_gateway/views.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/panel.js tests/unit/test_local_gateway_views.py tests/unit/test_api_changes.py tests/unit/test_local_gateway_move.py tests/unit/test_after.py tests/unit/test_page_words.py
git commit -m "Gateway: a strict switch per server"
```

---

### Task 3: New tools wait (2.2)

**Files:**
- Modify: `src/kitden/local_gateway/views.py:101-116` (`tools_view`: `"new": bool` per tool)
- Modify: `src/kitden/web/static/js/panel.js:374-386` (`toolRows`: a `New` flag)
- Test: `tests/unit/test_local_gateway_views.py`, `tests/frontend/panel.test.mjs`

**Interfaces:**
- Produces: a tool dict in `tools_view` has `"new": True` when the server is strict and no scope in the chain and no global rule has a state for that tool; else `False`. `toolRows` rows carry `flag: "New" | null`; the row's name line shows `New · off`.

- [ ] **Step 1: Write the failing tests**

```python
def test_in_strict_mode_an_unruled_tool_is_new_and_off(home):
    view = tools_view(settings_with_mode, {"github": [tool("list_issues"), tool("create_issue")]}, "github", [])
    assert [(t["name"], t["state"], t["new"]) for t in view["tools"]] == [("list_issues", "on", False), ("create_issue", "off", True)]


def test_outside_strict_mode_no_tool_is_new(home):
    assert not any(t["new"] for t in tools_view(settings_plain, tools, "github", [])["tools"])
```

```js
test('a new tool in strict mode is flagged', () => {
  const rows = toolRows({ server: 'github', state: 'on', strict: true, tools: [{ name: 'create_issue', description: '', state: 'off', new: true }] }, null);
  assert.equal(rows[1].flag, 'New');
});
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_local_gateway_views.py -v -k new` and `node --test tests/frontend/panel.test.mjs`
- [ ] **Step 3: Implement** in `tools_view` (use `own_state` over every scope of the chain plus global) and `toolRows` (`flag`), and draw the flag with `flag({ text: "New", level: "info" })` from `parts.js` next to the name.
- [ ] **Step 4: Run the tests**: PASS
- [ ] **Step 5: Commit**

```bash
git add src/kitden/local_gateway/views.py src/kitden/web/static/js/panel.js tests/unit/test_local_gateway_views.py tests/frontend/panel.test.mjs
git commit -m "Gateway: new tools wait in strict mode"
```

---

### Task 4: A switched-off tool is refused at once (2.3)

**Files:**
- Modify: `src/kitden/local_gateway/settings.py` (new `is_allowed`)
- Modify: `src/kitden/local_gateway/proxy.py:351-420` (`_Gateway`: keep `self.chain`; `call_tool` checks before forwarding; best-effort list-changed)
- Modify: `src/kitden/views/after.py:335` (the rule note)
- Test: `tests/unit/test_local_gateway_settings.py`, `tests/unit/test_local_gateway_proxy.py`, `tests/unit/test_after.py`

**Interfaces:**
- Produces: `is_allowed(home: Path, chain: Sequence[str], server: str, tool: str) -> bool`: reads `load_settings(home)` again and answers `state_in(..., server, None) == "on" and state_in(..., server, tool) == "on"`. In the proxy, `_find` stores `self.chain = chain`; `call_tool`, when `params.name` maps to `(server, tool)`, answers `_answer(f"{params.name} is turned off in Kitden.")` when `is_allowed` is false (run in a thread with `anyio.to_thread.run_sync`). Best effort: `_Gateway` remembers the rules file's `st_mtime` at `_find`; on a call, when it changed and the newly allowed set (from the cached tool lists, no server asked) differs from `self.names`, it sends the tool-list-changed notification once and remembers the new mtime. The rule review note becomes `"A tool turned off is refused at once. The client shows the new list in a new session."`

- [ ] **Step 1: Check the SDK**: find in mcp 2.3's `ServerSession` the method that sends `notifications/tools/list_changed` (search the installed package under `.venv` for `list_changed`); write `# checked 2026-10-21` with the method name in `proxy.py` where it is used.

- [ ] **Step 2: Write the failing tests**

```python
def test_is_allowed_reads_the_file_again(tmp_path):
    write_settings(tmp_path, {"servers": {"github": {}}, "rules": {"global": {}, "projects": {}}})
    assert is_allowed(tmp_path, [], "github", "echo") is True
    write_settings(tmp_path, {"servers": {"github": {}}, "rules": {"global": {"github": {"tools": {"echo": "off"}}}, "projects": {}}})
    assert is_allowed(tmp_path, [], "github", "echo") is False


def test_a_tool_on_under_a_server_off_is_refused(tmp_path):
    write_settings(tmp_path, {"servers": {"github": {}}, "rules": {"global": {"github": {"server": "off", "tools": {"echo": "on"}}}, "projects": {}}})
    assert is_allowed(tmp_path, [], "github", "echo") is False
```

```python
async def test_a_tool_turned_off_during_a_session_is_refused_on_its_next_call(home):
    # as test_a_call_reaches_the_upstream_server: list tools, call "echo" once (works), then
    # write the rule echo: off into gateway.json, call again:
    answer = await session.call_tool("echo", {"text": "hi"})
    assert answer.is_error and text(answer) == "echo is turned off in Kitden."
```

`tests/unit/test_after.py`: the rule note ends with `"A tool turned off is refused at once. The client shows the new list in a new session."` and no longer contains `"Applies to new sessions."` for a `gateway.rule` change (the move words keep theirs).

- [ ] **Step 3: Run them to see them fail**: `uv run pytest tests/unit/test_local_gateway_settings.py tests/unit/test_local_gateway_proxy.py tests/unit/test_after.py -v -k "allowed or refused or new_list"`
- [ ] **Step 4: Implement** as the interface says. The list-changed part is wrapped in `try/except Exception` and never fails a call.
- [ ] **Step 5: Run the tests**: PASS, and `uv run pytest tests/unit/test_local_gateway_proxy.py -v` whole.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/local_gateway/settings.py src/kitden/local_gateway/proxy.py src/kitden/views/after.py tests/unit/test_local_gateway_settings.py tests/unit/test_local_gateway_proxy.py tests/unit/test_after.py
git commit -m "Gateway: refuse a switched-off tool at once"
```

---

### Task 5: An unknown folder is said plainly (2.4)

**Files:**
- Modify: `src/kitden/web/static/js/panel.js:420-430` (`toolsSection` head, when no project is picked)
- Modify: `README.md` (Gateway section, one sentence)
- Test: `tests/unit/test_page_words.py`, `tests/unit/test_docs_words.py`

- [ ] **Step 1: Write the failing tests**: `panel.js` contains `"These switches also apply in folders Kitden does not know."`; README contains `"In a folder Kitden does not know as a project, the All projects switches apply."`.
- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**: in `toolsSection`, when `!state.project`, append `el("p", "muted", "These switches also apply in folders Kitden does not know.")` under the head; the README sentence in the gateway paragraph.
- [ ] **Step 4: Run the tests**: PASS
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/panel.js README.md tests/unit/test_page_words.py tests/unit/test_docs_words.py
git commit -m "Gateway: say what an unknown folder gets"
```

---

### Task 6: Reads and writes as a helper, and one batch switch (2.5, 1.5)

**Files:**
- Modify: `src/kitden/local_gateway/views.py` (new `WRITE_VERBS`, `tool_hint`, `rules_steps`; `tools_view` adds `hint`, `hint_from`)
- Modify: `src/kitden/changes/actions.py:389-391` (`GATEWAY_RULES = "gateway.rules"`)
- Modify: `src/kitden/web/app.py:835-837` (dispatch `GATEWAY_RULES`)
- Modify: `src/kitden/views/after.py` (new `_rules_words`)
- Modify: `src/kitden/web/static/js/panel.js:374-386` (`toolRows`: `hint`, `hintFrom`), `420-470` (the hint word per row; the button "Turn off every writing tool…")
- Test: `tests/unit/test_local_gateway_views.py`, `tests/unit/test_api_changes.py`, `tests/unit/test_after.py`, `tests/frontend/panel.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces: `WRITE_VERBS = ("write", "create", "delete", "remove", "update", "set", "send", "post", "put", "patch", "move", "rename", "upload", "execute", "run")`; `tool_hint(tool: dict) -> tuple[str, str | None]`: `("reads", "server")` when `annotations.readOnlyHint is True`; `("writes", "server")` when `readOnlyHint is False` or `destructiveHint is True`; `("may write", "name")` when there are no annotations and a whole word of the name (split on `_`, `-`, `.` and camel-case boundaries, lower-cased) is in `WRITE_VERBS`; else `("unknown", None)`. `tools_view` tools carry `"hint"` and `"hint_from"`. `rules_steps(home: Path, params: dict, projects: dict[str, str]) -> list[Step]` with `params = {"server": str, "tools": list[str], "state": "on" | "off", "project": str | None}` returning one `rule_step` per tool (same checks as `rule_steps`; an empty list raises `ValueError("Choose at least one tool.")`). Review words for `GATEWAY_RULES`: first line `"<n> tools of <server> will be off in <where>: a, b, c."`, then `"Hints come from the server and names are a guess; check the list."`, then `"For a real guarantee, give <server> a token that can only read."`, then the Task 4 note. Page: the hint word per row in muted text with hover `"from the server"` or `"by its name"`; the button `"Turn off every writing tool…"` sends `rules_steps` params with every tool whose hint is `writes` or `may write` and whose state is `on`; it is hidden when that list is empty.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("tool, expected", [
    ({"name": "read_file", "annotations": {"readOnlyHint": True}}, ("reads", "server")),
    ({"name": "search", "annotations": {"readOnlyHint": False}}, ("writes", "server")),
    ({"name": "delete_file", "annotations": {"destructiveHint": True}}, ("writes", "server")),
    ({"name": "create_issue"}, ("may write", "name")),
    ({"name": "uploadFile"}, ("may write", "name")),
    ({"name": "search"}, ("unknown", None)),
])
def test_tool_hints_come_from_annotations_then_names(tool, expected):
    assert tool_hint({"description": "", "inputSchema": {}, **tool}) == expected


@pytest.mark.parametrize("name", ["runway_status", "settle_bill", "posture", "putative"])
def test_verbs_match_whole_words_only(name):
    assert tool_hint({"name": name}) == ("unknown", None)


def test_rules_steps_make_one_step_per_tool(home):
    steps = rules_steps(home, {"server": "github", "tools": ["create_issue", "delete_issue"], "state": "off", "project": None}, {})
    assert [s.edit.key[-1] for s in steps] == ["create_issue", "delete_issue"]
```

`test_api_changes.py`: `test_gateway_rules_previews_one_change_with_several_steps`: POST preview with `gateway.rules` → the change has two steps; the after note has the three lines; apply and undo work.

```js
test('tool rows carry the hint and where it comes from', () => {
  const rows = toolRows({ server: 'github', state: 'on', strict: false, tools: [{ name: 'read_file', description: '', state: 'on', hint: 'reads', hint_from: 'server', new: false }] }, null);
  assert.equal(rows[1].hint, 'reads'); assert.equal(rows[1].hintFrom, 'server');
});
test('the batch switch takes the writing tools that are on', () => {
  const tools = [{ name: 'a', state: 'on', hint: 'writes' }, { name: 'b', state: 'off', hint: 'writes' }, { name: 'c', state: 'on', hint: 'may write' }, { name: 'd', state: 'on', hint: 'reads' }];
  assert.deepEqual(writingToolsOn(tools), ['a', 'c']);
});
```

`test_page_words.py`: `panel.js` contains `"Turn off every writing tool…"`, `"from the server"`, `"by its name"`.

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement** the Python side (`tool_hint` with a small word splitter, `rules_steps`, the action, the dispatch, `_rules_words`), then the page (`export function writingToolsOn(tools) -> string[]`, the hint word, the button that calls `review({ action: "gateway.rules", targets: [], params: { server, tools: writingToolsOn(answer.tools), state: "off", project: state.project || null } }, { back })`).
- [ ] **Step 4: Run the tests**: PASS, and `node --test tests/frontend/*.test.mjs`.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/local_gateway/views.py src/kitden/changes/actions.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/panel.js tests/unit/test_local_gateway_views.py tests/unit/test_api_changes.py tests/unit/test_after.py tests/frontend/panel.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: reads and writes as a helper, one switch for writing tools"
```

---

### Task 7: Calls are counted (2.6)

**Files:**
- Modify: `src/kitden/local_gateway/settings.py` (`CALLS_FILE = "gateway-calls.json"`, `load_calls`, `count_call`)
- Modify: `src/kitden/local_gateway/proxy.py:369-384` (`call_tool`: count after a forwarded call)
- Modify: `src/kitden/local_gateway/views.py:101-116` (`tools_view`: `"calls"` per tool)
- Modify: `src/kitden/web/static/js/panel.js` (`callsText`, the hover text)
- Test: `tests/unit/test_local_gateway_settings.py`, `tests/unit/test_local_gateway_proxy.py`, `tests/unit/test_local_gateway_views.py`, `tests/frontend/panel.test.mjs`

**Interfaces:**
- Produces: `load_calls(home) -> dict[str, dict[str, dict]]` (`{server: {tool: {"count": int, "last": "<ISO minute>"}}}`; a missing or broken file is `{}`); `count_call(home: Path, server: str, tool: str, now: datetime | None = None) -> None` (read, add one, set `last`, `write_atomic` into the 0700 data folder; raises `OSError` only). In the proxy, after `self.upstreams.call(...)` returns, `count_call` runs in a thread inside `try/except OSError` that says one plain line `"Kitden could not count the call to <server>."` on stderr. `tools_view` tools carry `"calls": {"count": int, "last": str} | None`. Page: `export function callsText(calls, now) -> string | null`: `"Called 12 times, last today 14:02"`, `"Called once, last 20 Oct 09:15"`, `null` without calls; the text is the tool row's `title`.

- [ ] **Step 1: Write the failing tests**

```python
def test_count_call_adds_one_and_keeps_the_last_time(tmp_path):
    now = datetime(2026, 10, 21, 14, 2, 30, tzinfo=UTC)
    count_call(tmp_path, "github", "echo", now)
    count_call(tmp_path, "github", "echo", now)
    assert load_calls(tmp_path) == {"github": {"echo": {"count": 2, "last": "2026-10-21T14:02Z"}}}


def test_a_broken_calls_file_reads_as_empty(tmp_path):
    (data_dir(tmp_path)).mkdir(parents=True); (data_dir(tmp_path) / CALLS_FILE).write_text("[1")
    assert load_calls(tmp_path) == {}
```

```python
async def test_a_call_is_counted(home):
    # as test_a_call_reaches_the_upstream_server, then:
    assert load_calls(home)["echo"]["echo"]["count"] == 1


async def test_a_broken_calls_file_does_not_stop_a_call(home, capsys):
    # make the calls file a folder so the write fails
    ...
    assert not answer.is_error
    assert "Kitden could not count the call to echo." in capsys.readouterr().err
```

```js
test('calls text says how many and when', () => {
  const now = new Date('2026-10-21T15:00:00Z');
  assert.equal(callsText({ count: 12, last: '2026-10-21T14:02Z' }, now), 'Called 12 times, last today 14:02');
  assert.equal(callsText({ count: 1, last: '2026-10-20T09:15Z' }, now), 'Called once, last 20 Oct 09:15');
  assert.equal(callsText(null, now), null);
});
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement** as the interface says; times are UTC in the file and shown in the browser's local time by `callsText`.
- [ ] **Step 4: Run the tests**: PASS
- [ ] **Step 5: Commit**

```bash
git add src/kitden/local_gateway/settings.py src/kitden/local_gateway/proxy.py src/kitden/local_gateway/views.py src/kitden/web/static/js/panel.js tests/unit/test_local_gateway_settings.py tests/unit/test_local_gateway_proxy.py tests/unit/test_local_gateway_views.py tests/frontend/panel.test.mjs
git commit -m "Gateway: count calls per tool"
```

---

### Task 8: Docs, hand check and roadmap for Part 2

**Files:**
- Modify: `README.md` (the Kitden gateway section: strict mode, refusal at once, the hint words and the batch switch, counts, the token line)
- Modify: `docs/development.md` ("Check before a release": strict mode on, a new session sees only the allowed tools, a tool turned off is refused in the same session, Undo both; "Gateways": the three files in the data folder and what each is)
- Modify: `ROADMAP.md` ("### Not released yet")

- [ ] **Step 1: Write the README paragraph** (plain, at most six sentences).
- [ ] **Step 2: Add the hand-check steps** to `docs/development.md`, numbered after the existing four.
- [ ] **Step 3: Update ROADMAP.md**.
- [ ] **Step 4: Run all checks**: `uv run pytest -q && uv run ruff check . && node --test tests/frontend/*.test.mjs`
- [ ] **Step 5: Do the hand check once** in Claude Code, Codex and Cursor on a throwaway project; note the date in `docs/development.md` next to the steps.
- [ ] **Step 6: Commit**

```bash
git add README.md docs/development.md ROADMAP.md
git commit -m "Docs: Part 2 of the review follow-up"
```
