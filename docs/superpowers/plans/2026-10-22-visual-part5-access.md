# Part 5: Access — routes, origins and honest limits — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Gateway page shows every route (held servers through the Kitden gateway, direct
entries beside them), the clients each held server reaches, where each tool's state comes from,
reviews that name what they keep and what they cannot promise, rules for folders that are gone,
and call counts a keyboard user can read.

**Architecture:** The rule data grows by three fields per row in `local_gateway/views.py`
(`origin`, `origin_from`, `effective`); the batch review gets a server-side checklist that
round-trips through preview like Add missing's chosen keys; rules for folders no client lists
get one new change action through the engine. The page draws from these: a pure `routeLayout`
in `gateway.js` places the diagram, pure helpers in `tools.js`, `review.js` (Part 3's modules)
and `parts.js` word the rows.

**Tech Stack:** Python 3.13, Starlette; plain ES modules, one CSS file; pytest on sandbox homes
and the Part 1 samples; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 5 (5.1–5.6),
built on concept §7 (`docs/research/visual-management-ux-concept-2026-10-22.md`). Master plan:
`docs/superpowers/plans/2026-10-22-visual-management.md` (its Rules and "Names that cross part
boundaries" bind this plan; this part defines tool row fields `origin` in
`"project" "parent" "global" "default" "strict"` and `origin_from: str | None`).

## Global Constraints

- `AGENTS.md` in full; code, comments, UI text and docs in simple English.
- Every write goes through the change engine: preview → Apply with a backup → verify → Undo. The
  new "Remove" for lost rules is a settings step (`settings_step`), never a direct write.
- Main pages show a name, the client, a state and an action. A folder's full path is only its
  hover text; addresses and commands stay in Details.
- `docs/design.md` changes in the same commit as the page change it describes; new page words
  are pinned in `tests/unit/test_page_words.py` in that commit; a changed word changes its pin.
- Spec copy, exactly: the route label `Direct` (never amber: direct is not a fault); the limit
  line stays "The gateway controls only the servers in it. Direct entries and terminal tools are
  outside it."; origin words "All projects", "This project", "From <parent folder>", "On by
  default", "New · waits"; the Strict row "Only tools that are on are offered; a new tool
  waits."; switch words stay On and Off; "Use <parent>" whenever the project has
  its own rule; "Not sure"; "Keeps on: read, list, search."; "a call already running is not
  stopped"; with a project picked "A session gets these switches only when it runs in this
  project's folder."; with All projects "These switches also apply in folders Kitden does not
  know."; the group "Rules for folders Kitden no longer finds", each with Remove; calls
  "12 calls · last today 14:02".
- Motion (design.md): lines draw once and rest; nothing loops; reduced motion shows them at once;
  total stagger under 500 ms. `tests/unit/test_page_words.py::test_gateway_wires_do_not_fake_traffic`
  fails if the letters `flow` appear anywhere in `gateway.js`: never write "overflow" or
  "workflow" there, not even in a comment.
- Tests use `make_home(...)`/`write_cursor_fixture_state(home)` or `build_demo_home(root, size)`
  (Part 1). No real client command, real MCP server, Keychain or network.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`,
  `node --test tests/frontend/*.test.mjs`. Stage files by name. Subject plain, one to three
  lines, ending with the co-author line the session gives.
- `ROADMAP.md`: while `git status` shows it modified and not by this part, no task edits or
  stages it; Task 8 then writes the lines into its report.
- Line numbers are hints; find code by name. Parts 2–4 change `parts.js` and the side panel
  before this part, and Part 3 splits `panel.js`: the tool list (`toolRows`, `callsText`,
  `writingToolsOn`, `toolsSection`) is in `tools.js`, `changeWords`, `DONE_WORDS` and
  `showReview` in `review.js`. New node tests go in `tests/frontend/tools.test.mjs` (create it
  with `panel.test.mjs`'s header stubs) or `review.test.mjs` and import from that module;
  existing tests in `panel.test.mjs` are edited where they are.
- Sample facts are Part 1's "Sample contract": `~/work/atlas/web` inside `~/work/atlas`, whose
  rule turns `files.write_file` off; `files.search_files` has no hint and is on for all projects;
  `tracker` is strict and `tracker.export_report` waits.

## Review Focus

1. A project rule equal to the one it would inherit: the row says "This project", offers
   "Use <parent>", and the preview removes the rule instead of "Nothing to change" (Task 1
   `test_an_equal_project_rule_is_this_projects_and_can_be_removed`; Task 2 node test
   'a row with its own rule offers its parent even when the state is the same').
2. A server that is off in the picked project, often by a parent project's rule: each tool shows
   off with "Server off", its switch cannot be pressed, and the writing batch is not offered
   (Task 1 `test_a_tool_of_a_server_that_is_off_is_off_in_effect`; Task 2 node test
   'a tool of a server that is off shows off and cannot be switched').
3. Many servers with long names (the `large` sample): the diagram draws at most six held and six
   direct servers, then "+N more"; names end in "…"; its height stops growing (Task 6
   `test_the_large_sample_gives_every_direct_row_its_columns`; Task 7 node tests
   'the diagram grows with its servers, then stops at six of each with +N more' and
   'a long server name is cut with … and keeps its whole name in its label').
4. A direct server in the Claude Desktop Code tab, or one that comes with a plugin: counted as a
   Claude Code direct route, never dropped (Task 6 `test_direct_rows_name_the_client_columns_they_reach`;
   Task 7 node test 'a Desktop Code tab entry is a direct route of Claude Code').
5. A known project whose folder is missing (a client still lists it): its rules are not under
   "Rules for folders Kitden no longer finds", and Remove is refused for it (Task 5
   `test_a_listed_project_with_a_missing_folder_keeps_its_rules`).

---

### Task 1: Each rule row says who decides, and the server switch counts (5.3, data)

**Files:**
- Modify: `src/kitden/local_gateway/views.py` (`_states`, `tools_view`)
- Create: `tests/unit/test_gateway_access.py`
- Modify: `tests/unit/test_local_gateway_views.py` (`test_tools_api_marks_project_differences`: the exact tool dict gains `"effective": "on", "origin": "default", "origin_from": None`)

**Interfaces:**
- Consumes: `kitden.demo.build_demo_home(root: Path, size: str) -> Path` (Part 1). In the
  `medium` sample `~/work/atlas/web` sits inside `~/work/atlas`; `atlas` turns
  `files.write_file` off, `atlas/web` turns `files.search_files` off, all projects turn
  `files.delete_file` off, and `tracker` is strict with `list_issues` and `create_issue` on.
- Produces: `_states(settings, server, tool, chain) -> dict` with keys `state`, `differs`,
  `follows` (as today) plus `origin: "project" | "parent" | "global" | "default" | "strict"` and
  `origin_from: str | None` (the deciding project's folder name, only for `"parent"`). Rule, in
  order: the picked project (`chain[0]`) has its own state → `"project"`; else
  `deciding_project(settings, chain[1:], …)` → `"parent"`; else the global rule has a state →
  `"global"`; else a tool of a strict server → `"strict"`; else `"default"`. `tools_view(...)`
  carries both at the top (the whole server) and on each tool, and each tool gains
  `effective: "on" | "off"`: `"off"` when the server's state along the chain is off, else the
  tool's `state`. `held_servers` is unchanged (it picks its own keys).

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_gateway_access.py` (its own `home`
  fixture, the same as in `test_local_gateway_views.py`, so ruff sees no shadowed import; from
  there import `FILES`, `POST`, `hold`, `tool`, `echo`, `add_kitden`, `page_for`, `project`,
  `project_id`, `rule_preview`; the rest from `kitden.demo`, `kitden.gateways`,
  `kitden.local_gateway.project`, `kitden.local_gateway.settings`, `kitden.local_gateway.views`,
  `kitden.views.inventory`; later tasks add their own imports)

```python
SITE, WEB = "/w/site", "/w/site/web"


def settings_with(global_rules, projects):
    return {"servers": {"echo": {"command": "echo"}}, "rules": {"global": global_rules, "projects": projects}}


ECHO_TOOLS = {"echo": [tool(n) for n in ("echo", "slow", "clash", "where")]}


def test_each_tool_says_where_its_state_comes_from():
    settings = settings_with(
        {"echo": {"tools": {"slow": "off"}}},
        {SITE: {"echo": {"tools": {"clash": "off"}}}, WEB: {"echo": {"tools": {"where": "on"}}}},
    )
    web = tools_view(settings, ECHO_TOOLS, "echo", [WEB, SITE])
    assert [(t["name"], t["origin"], t["origin_from"]) for t in web["tools"]] == [
        ("echo", "default", None),
        ("slow", "global", None),
        ("clash", "parent", "site"),
        ("where", "project", None),
    ]
    assert (web["origin"], web["origin_from"]) == ("default", None)
    everywhere = tools_view(settings, ECHO_TOOLS, "echo", [])
    assert [t["origin"] for t in everywhere["tools"]] == ["default", "global", "default", "default"]


def test_an_equal_project_rule_is_this_projects_and_can_be_removed(home):
    settings = settings_with({"echo": {"tools": {"slow": "off"}}}, {WEB: {"echo": {"tools": {"slow": "off"}}}})
    slow = tools_view(settings, ECHO_TOOLS, "echo", [WEB, SITE])["tools"][1]
    assert (slow["origin"], slow["differs"], slow["state"]) == ("project", False, "off")
    # On the page the same rule can go: the review says what the project then follows.
    website = project(home, "website")
    hold(home, {"echo": echo()}, {"global": {"echo": {"tools": {"slow": "off"}}}, "projects": {website: {"echo": {"tools": {"slow": "off"}}}}})
    save_tools(home, "echo", [tool("echo"), tool("slow")])
    add_kitden(home, "cursor")
    with page_for(home) as page:
        answer = rule_preview(page, server="echo", tool="slow", state=None, project=project_id(page, website))
    assert answer.status_code == 200, answer.json()
    assert answer.json()["after"][0]["word"] == "Follows all projects"


def test_a_tool_that_waits_in_strict_mode_has_the_strict_origin():
    settings = settings_with({"echo": {"mode": "strict", "tools": {"slow": "on"}}}, {})
    tools = {"echo": [tool("echo"), tool("slow")]}
    view = tools_view(settings, tools, "echo", [])
    assert [(t["name"], t["origin"], t["state"], t["new"]) for t in view["tools"]] == [
        ("echo", "strict", "off", True),
        ("slow", "global", "on", False),
    ]


def test_a_tool_of_a_server_that_is_off_is_off_in_effect():
    settings = settings_with({"echo": {"tools": {"slow": "off"}}}, {SITE: {"echo": {"server": "off"}}})
    web = tools_view(settings, ECHO_TOOLS, "echo", [WEB, SITE])
    assert (web["state"], web["origin"], web["origin_from"]) == ("off", "parent", "site")
    assert {t["name"]: (t["state"], t["effective"]) for t in web["tools"]} == {
        "echo": ("on", "off"), "slow": ("off", "off"), "clash": ("on", "off"), "where": ("on", "off"),
    }
    everywhere = tools_view(settings, ECHO_TOOLS, "echo", [])
    assert all(t["effective"] == t["state"] for t in everywhere["tools"])


def test_the_medium_sample_names_the_parent_project_that_decides(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    settings, tools = load_settings(home), load_tools(home)
    known = [p.path for p in build_inventory(home).projects]
    chain = project_chain(str(home / "work/atlas/web"), home, known)  # [atlas/web, atlas]
    files = tools_view(settings, tools, "files", chain)["tools"]
    assert {t["name"]: (t["origin"], t["origin_from"]) for t in files} == {
        "read_file": ("default", None),
        "write_file": ("parent", "atlas"),
        "delete_file": ("global", None),
        "search_files": ("project", None),
    }
    tracker = tools_view(settings, tools, "tracker", [])["tools"]
    assert {t["name"]: t["origin"] for t in tracker} == {
        "list_issues": "global", "create_issue": "global", "export_report": "strict",
    }
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_gateway_access.py -v` → KeyError `origin` / `effective`.
- [ ] **Step 3: Implement** `_states` (the rule above) and `effective` in `tools_view` (one
  `state_in(settings, chain, server, None)` per call). Update the exact dict in
  `test_tools_api_marks_project_differences`.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_gateway_access.py tests/unit/test_local_gateway_views.py -v` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/local_gateway/views.py tests/unit/test_gateway_access.py tests/unit/test_local_gateway_views.py
git commit -m "Gateway: each rule row says who decides it"
```

---

### Task 2: The tool list says why, and shows its calls (5.3, 5.5 sessions line, 5.6)

**Files:**
- Modify: `src/kitden/web/static/js/parts.js` (new `TOOL_ORIGIN_WORDS`, `originText`)
- Modify: `src/kitden/web/static/js/tools.js` (Part 3's module: `toolRows`, `callsText`, `writingToolsOn`, `toolsSection`)
- Modify: `docs/design.md` (Gateway table, "Tool switches" row)
- Test: `tests/frontend/parts.test.mjs`, `tests/frontend/tools.test.mjs` (create), `tests/frontend/panel.test.mjs` (existing tool tests), `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 1 fields; `ALL_PROJECTS = "All projects"` in `parts.js` (Part 2).
- Produces:
  - `TOOL_ORIGIN_WORDS = { project: "This project", global: ALL_PROJECTS, default: "On by default", strict: "New · waits" }`
    (not `ORIGIN_WORDS`: that is Part 2's Python table of cell origins, a different thing)
    and `originText({ origin, origin_from }) -> string | null` (`"parent"` → `` `From ${origin_from}` ``; unknown → null).
  - `toolRows(answer, where)` rows: `{ key, tool, name, description, on, disabled, hint, hintFrom, calls, origin, own, differs, follows, label, title }`.
    `on`: a tool's `effective !== "off"`, the whole server's `state !== "off"`. `disabled` and
    `title` (`` `${server} is off in ${place}` ``) only for a tool when `answer.state === "off"`;
    then `origin` is `"Server off"`, else `originText(entry)` (the whole server row too).
    `own`: `entry.origin === "project"`. The `flag` field goes: "New · waits" replaces the "New" flag.
  - `callsText(calls, now) -> string | null`: `"12 calls · last today 14:02"`, `"1 call · last 20 Oct 09:15"`, null without calls.
  - `writingToolsOn(tools)`: the names whose `effective === "on"` and whose hint is "writes" or "may write".
  - In `toolsSection`: the origin word is a quiet `span.muted.hint.origin` after the hint word;
    the calls text is a visible `div.why.calls` under the description (no more `node.title = row.calls`);
    the "Use {follows}" button shows when `row.own`, the "Differs from {follows}" flag only when
    `row.differs`; a `disabled` switch gets `disabled` and its `title`; the line under the heading
    is the sessions line (exact copy in Global Constraints).
  - The Strict row (`strictRow` in `toolsSection`; spec 5.4): its line reads
    "Only tools that are on are offered; a new tool waits." (was "Only tools you turned on are
    offered; a new tool waits."), and its switch's `aria-label` reads
    "Strict: only tools that are on" (was "Strict: only tools you turned on"): strict mode turns
    the known tools on for you, so the old words overstate.

- [ ] **Step 1: Write the failing tests**

```js
// parts.test.mjs
const { originText } = await import('../../src/kitden/web/static/js/parts.js');
test('a rule row says where its state comes from in one word', () => {
  assert.equal(originText({ origin: 'project' }), 'This project');
  assert.equal(originText({ origin: 'parent', origin_from: 'website' }), 'From website');
  assert.equal(originText({ origin: 'global' }), 'All projects');
  assert.equal(originText({ origin: 'default' }), 'On by default');
  assert.equal(originText({ origin: 'strict' }), 'New · waits');
  assert.equal(originText({}), null);
});
```

```js
// tools.test.mjs (new; header stubs as panel.test.mjs; import toolRows, writingToolsOn from tools.js)
const rule = (fields) => ({ description: '', differs: false, follows: null, origin: 'default', origin_from: null, ...fields });
test('a row with its own rule offers its parent even when the state is the same', () => {
  const answer = { server: 'echo', ...rule({ state: 'on' }), tools: [{ name: 'slow', ...rule({ state: 'off', effective: 'off', origin: 'project', follows: 'website' }) }] };
  const [server, slow] = toolRows(answer, 'web');
  assert.deepEqual([slow.origin, slow.own, slow.differs, slow.follows, slow.on], ['This project', true, false, 'website', false]);
  assert.deepEqual([server.origin, server.own], ['On by default', false]);
});
test('a tool of a server that is off shows off and cannot be switched', () => {
  const tools = [{ name: 'push', ...rule({ state: 'on', effective: 'off', hint: 'writes', hint_from: 'server' }) }];
  const answer = { server: 'echo', ...rule({ state: 'off', origin: 'parent', origin_from: 'website', follows: 'website' }), tools };
  const [server, push] = toolRows(answer, 'web');
  assert.deepEqual([server.on, server.disabled, server.origin], [false, false, 'From website']);
  assert.deepEqual([push.on, push.disabled, push.origin, push.title], [false, true, 'Server off', 'echo is off in web']);
  assert.deepEqual(writingToolsOn(tools), []);
});
```

  Update in `panel.test.mjs` (existing tests, edited where they are): 'calls text says how many
  and when' takes the new words, `'12 calls · last today 14:02'` and `'1 call · last 20 Oct 09:15'`
  (was "Called 12 times, last today 14:02" and "Called once, …"); the fixtures of 'a held server
  lists the whole server first…' and 'the batch switch takes the writing tools that are on' carry
  `effective` (equal to `state`); 'a new tool in strict mode is flagged' becomes 'a new tool in
  strict mode says it waits': `rows[1].origin === 'New · waits'` for `origin: 'strict'`,
  `rows[2].origin === 'All projects'` for `origin: 'global'`.

```python
# test_page_words.py
def test_tool_rows_say_why_and_show_calls_without_hover():
    tools, parts = script("tools.js"), script("parts.js")
    for words in ('"This project"', '"On by default"', '"New · waits"', "From ${"):
        assert words in parts, words
    assert '"Server off"' in tools and "node.title = row.calls" not in tools
    assert "A session gets these switches only when it runs in this project's folder." in tools
    assert "These switches also apply in folders Kitden does not know." in tools
    assert "Only tools that are on are offered; a new tool waits." in tools
    assert "tools you turned on" not in panel()
```

  Update `test_the_tool_list_has_a_strict_switch`: its pin becomes
  `"Strict: only tools that are on" in panel()` (Part 3's helper; the other two pins stay).

- [ ] **Step 2: Run them to see them fail**: `node --test tests/frontend/parts.test.mjs tests/frontend/tools.test.mjs tests/frontend/panel.test.mjs`, `uv run pytest tests/unit/test_page_words.py -v`.
- [ ] **Step 3: Implement** as the interface says; keep `` `Differs from ${row.follows}` `` and
  `` `Use ${row.follows}` `` (pinned). Update design.md's "Tool switches" row: each row has its
  hint word, then a quiet origin word ("All projects", "This project", "From {folder}", "On by
  default", "New · waits"); "Use all projects" or "Use {project}" whenever the project has its own
  rule, "Differs from …" only when that rule changes the state; a tool of a server that is off
  reads "Server off" and its switch rests off and cannot be pressed; under the description a
  quiet "12 calls · last today 14:02"; the line under the heading names where the switches apply;
  the Strict row comes first and says "Only tools that are on are offered; a new tool waits.";
  with a project picked its switch rests and says "Set for all projects".
- [ ] **Step 4: Run the tests** → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/web/static/js/parts.js src/kitden/web/static/js/tools.js docs/design.md tests/frontend/parts.test.mjs tests/frontend/tools.test.mjs tests/frontend/panel.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: tools say where their state comes from and show their calls"
```

---

### Task 3: Reviews name what strict keeps on and what a switch cannot stop (5.4, words)

**Files:**
- Modify: `src/kitden/views/after.py` (`AT_ONCE`, new `_strict_switch_line`, `_strict_words`)
- Test: `tests/unit/test_after.py`, `tests/unit/test_local_gateway_views.py` (its `AT_ONCE` copy)

**Interfaces:**
- Produces:
  - `AT_ONCE = "A tool turned off is refused at once; a call already running is not stopped. The client shows the new list in a new session."`
    (the one switch, the batch and strict on all end with it).
  - `_strict_switch_line(server: str, kept: list[str] | None) -> str` for the strict switch turned
    on. `kept` None (Kitden does not know the tools): today's "Strict mode on for {server}: its
    tools show as off until you turn them on. {GUARANTEE}". A list: "Strict mode on for {server}:
    a new tool waits until you turn it on. Keeps on: a, b, c. {GUARANTEE}" ("Keeps on: …." left
    out when the list is empty). `kept` = every cached tool of the server whose global rule is
    not "off" (they get or keep an "on" rule; see `strict_steps`), in cache order.
  - `_strict_line` stays for strict off and for a move (a Codex allowlist): its words do not change.

- [ ] **Step 1: Write the failing tests** (`_strict_note` takes `tools: list[str]` — empty means
  no tool list — and `rules: dict | None = None`; None keeps today's rules: none when turning
  on, strict mode when turning off)

```python
NEW_AT_ONCE = (
    "A tool turned off is refused at once; a call already running is not stopped. "
    "The client shows the new list in a new session."
)


def test_strict_on_names_the_tools_it_keeps_on(tmp_path, monkeypatch):
    note = _strict_note(tmp_path, monkeypatch, True, ["list_issues", "search"])
    assert note == (
        "Strict mode on for github: a new tool waits until you turn it on. "
        f"Keeps on: list_issues, search. {GUARANTEE} {NEW_AT_ONCE}"
    )


def test_strict_on_does_not_keep_a_tool_that_is_off_for_all_projects(tmp_path, monkeypatch):
    rules = {"global": {"github": {"tools": {"create_issue": "off"}}}}
    note = _strict_note(tmp_path, monkeypatch, True, ["list_issues", "create_issue"], rules)
    assert "Keeps on: list_issues." in note and "create_issue" not in note
```

  Update the literal strings of `test_a_rule_says_a_tool_turned_off_is_refused_at_once` and
  `test_turning_off_several_tools_names_them_and_says_names_are_a_guess` to `NEW_AT_ONCE`;
  `test_strict_on_says_only_turned_on_tools_are_offered` is replaced by the first test above;
  `test_strict_on_without_a_tool_list_says_its_tools_show_as_off` keeps its words; the move test
  `test_a_move_with_a_codex_allowlist_says_strict_mode_not_server_off` stays green unchanged.
  In `test_local_gateway_views.py`, `AT_ONCE` becomes the new sentence.

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_after.py -v`.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_after.py tests/unit/test_local_gateway_views.py -v` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/views/after.py tests/unit/test_after.py tests/unit/test_local_gateway_views.py
git commit -m "Gateway reviews: strict names the tools it keeps on; a running call is not stopped"
```

---

### Task 4: "Turn off every writing tool…" becomes a checklist (5.4)

**Files:**
- Modify: `src/kitden/local_gateway/views.py` (new `writing_checklist`)
- Modify: `src/kitden/web/app.py` (`preview`, the `GATEWAY_RULES` branch; the answer gains `checklist`)
- Modify: `src/kitden/web/static/js/review.js` (Part 3's module: new `checklistGroups`, `chosenTools`, `checklistSection`; `showReview` appends it when `change.checklist`)
- Modify: `docs/design.md` (Gateway table: a new row "Writing tools review")
- Test: `tests/unit/test_gateway_access.py`, `tests/frontend/review.test.mjs` (Part 3's), `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 1 (`effective`), Task 2 (`writingToolsOn`), Task 3 (`AT_ONCE`). The pattern of
  Add missing's chosen keys: a changed box cancels this preview and asks again with the new
  choice; with nothing chosen there is nothing to preview and Apply waits.
- Produces:
  - `writing_checklist(settings: dict, tools: dict, server: str, chain: list[str], chosen: list[str]) -> list[dict]`:
    in cache order, every tool of `server` that is on along `chain` (`state_in`) and whose
    `tool_hint` is not "reads", plus any tool in `chosen`; each
    `{"name", "hint", "hint_from", "chosen": name in chosen}`.
  - Preview answer of `gateway.rules` with `state` "off": `"checklist": [...]` (chain from the
    project id in `params` through `_chain`). `params.tools` stays the chosen list.
  - `checklistGroups(checklist) -> [{ title, items: [{ name, label, chosen }] }]`: "Writes or may
    write" (label `` `${name} · ${hint}, ${HINT_FROM[hint_from]}` ``) then "Not sure" (hint
    "unknown", label the name); empty groups left out.
  - `chosenTools(checklist, name, checked) -> string[]`, in checklist order.
  - `checklistSection(change, previewBody, note, apply, back)`: one fieldset per group; a change
    cancels the preview (`cancelPreview()`, `change.state = "cancelled"`, Apply disabled); with
    none chosen it shows "Choose at least one tool."; else
    `review({ ...previewBody, params: { ...previewBody.params, tools: chosen } }, { note, back })`
    and focus returns to the same box (`data-key` = the tool name).

- [ ] **Step 1: Write the failing tests**

```python
def rules_preview(page, **params):
    return page.post("/api/changes/preview", json={"action": "gateway.rules", "params": params}, headers=POST)


def test_the_writing_review_is_a_checklist_with_not_sure(home):
    hold(home, {"github": echo()}, {"global": {"github": {"tools": {"delete_repo": "off"}}}})
    reads = {**tool("list_issues"), "annotations": {"readOnlyHint": True}}
    wipe = {**tool("wipe"), "annotations": {"destructiveHint": True}}
    save_tools(home, "github", [reads, tool("create_issue"), wipe, tool("delete_repo"), tool("search")])
    add_kitden(home, "cursor")
    with page_for(home) as page:
        first = rules_preview(page, server="github", tools=["create_issue", "wipe"], state="off", project=None).json()
        # A tool that reads is not listed; one already off is not listed.
        assert first["checklist"] == [
            {"name": "create_issue", "hint": "may write", "hint_from": "name", "chosen": True},
            {"name": "wipe", "hint": "writes", "hint_from": "server", "chosen": True},
            {"name": "search", "hint": "unknown", "hint_from": None, "chosen": False},
        ]
        page.post(f"/api/changes/{first['id']}/cancel", headers=POST)
        again = rules_preview(page, server="github", tools=["create_issue", "wipe", "search"], state="off", project=None).json()
        assert [s["name"] for s in again["steps"]] == ["create_issue", "wipe", "search"]
        assert [c["chosen"] for c in again["checklist"]] == [True, True, True]


def test_the_medium_sample_puts_its_unknown_tool_under_not_sure(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    settings, tools = load_settings(home), load_tools(home)
    # Part 1: read_file reads; write_file writes; delete_file is off for all projects;
    # search_files has no hint and is on for all projects.
    assert writing_checklist(settings, tools, "files", [], []) == [
        {"name": "write_file", "hint": "writes", "hint_from": "server", "chosen": False},
        {"name": "search_files", "hint": "unknown", "hint_from": None, "chosen": False},
    ]
```

```js
// tests/frontend/review.test.mjs (import checklistGroups, chosenTools from review.js)
test('the writing review groups the tools that write and the ones it is not sure of', () => {
  const checklist = [
    { name: 'create_issue', hint: 'may write', hint_from: 'name', chosen: true },
    { name: 'wipe', hint: 'writes', hint_from: 'server', chosen: true },
    { name: 'search', hint: 'unknown', hint_from: null, chosen: false },
  ];
  assert.deepEqual(checklistGroups(checklist), [
    { title: 'Writes or may write', items: [
      { name: 'create_issue', label: 'create_issue · may write, by its name', chosen: true },
      { name: 'wipe', label: 'wipe · writes, from the server', chosen: true },
    ] },
    { title: 'Not sure', items: [{ name: 'search', label: 'search', chosen: false }] },
  ]);
  assert.deepEqual(chosenTools(checklist, 'search', true), ['create_issue', 'wipe', 'search']);
  assert.deepEqual(chosenTools(checklist, 'create_issue', false), ['wipe']);
  assert.deepEqual(chosenTools(checklist.slice(0, 1), 'create_issue', false), []);
});
```

```python
def test_the_writing_review_is_a_checklist():
    review = script("review.js")
    for words in ('"Writes or may write"', '"Not sure"', "Choose at least one tool.", "change.checklist"):
        assert words in review, words
    assert "Turn off every writing tool…" in script("tools.js")
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**. Design.md row "Writing tools review": tools that write or may write
  are checked, each with where its hint comes from; tools Kitden is not sure about are listed
  unchecked under "Not sure"; a change previews again; with none checked, Apply waits; the
  review keeps the token advice and says a running call is not stopped.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_gateway_access.py tests/unit/test_page_words.py -v` and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/local_gateway/views.py src/kitden/web/app.py src/kitden/web/static/js/review.js docs/design.md tests/unit/test_gateway_access.py tests/frontend/review.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: the writing tools review is a checklist with Not sure"
```

---

### Task 5: Rules for folders Kitden no longer finds (5.5)

**Files:**
- Modify: `src/kitden/changes/actions.py` (`GATEWAY_FORGET = "gateway.forget"  # the rules of a folder no client lists as a project leave the settings`)
- Modify: `src/kitden/local_gateway/views.py` (new `lost_rules`, `forget_steps`)
- Modify: `src/kitden/views/gateway_view.py` (`gateway_view(..., lost: list[dict] | None = None)`)
- Modify: `src/kitden/web/app.py` (`_gateway_view` passes `lost`; `preview` gains the `GATEWAY_FORGET` branch)
- Modify: `src/kitden/views/after.py` (new `_forget_words`; `after_words` dispatches to it)
- Modify: `src/kitden/web/static/js/gateway.js` (`kitdenCard` appends `lostRules(gateway)`)
- Modify: `src/kitden/web/static/js/review.js` (Part 3's module: `changeWords` title and done, `DONE_WORDS`, and `gateway.forget` added to Part 3's `PLACE_IN_TITLE`, since the title names its folder), `src/kitden/web/static/js/parts.js` (`ACTION_WORDS`, `changeTitle`)
- Modify: `docs/design.md` (Gateway table, "Kitden gateway card" row)
- Test: `tests/unit/test_gateway_access.py`, `tests/frontend/review.test.mjs` (Part 3's), `tests/frontend/parts.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces:
  - `lost_rules(settings: dict, known: list[str]) -> list[dict]`: each project key of
    `rules.projects` that is not in `known` and sets a state for at least one server or tool,
    as `{"path": str, "folder": Path(path).name, "servers": sorted names with a state}`, sorted
    by folder, case-insensitive. (`known` = `[p.path for p in inventory.projects]`, the same list
    the gateway uses, so a listed project whose folder is missing stays known.)
  - `forget_steps(home: Path, params: dict, known: list[str]) -> list[Step]`: `params["folder"]`
    is a path; one `settings_step(home, ("rules", "projects", path), ABSENT, Path(path).name)`.
    Refusals (`ValueError`): a known path → "This folder is a known project; its rules are in
    use."; a path without rules → "Kitden has no rules for this folder."
  - `gateway_view`: the Kitden gateway's dict gains `"lost_rules": lost` only when `lost` is
    not empty (as `problem`), so the exact dicts in `test_local_gateway_views.py` stay.
  - `_forget_words(change) -> [{"note": f"No client lists {folder} as a project now, so these rules apply in no session."}]`.
  - Page: a quiet section on the Kitden card after "In the gateway":
    `` `Rules for folders Kitden no longer finds · ${n}` ``, one row each: the folder in mono
    (its full path only as hover text), its servers as quiet text, and `"Remove…"` →
    `review({ action: "gateway.forget", targets: [], params: { folder: rule.path } })`.
    Review title `` `Remove the rules for ${folder}` ``, done `` `Removed the rules for ${folder}` ``,
    with no scope words after them (the preview's `target` is `"all"` for this settings step, and
    Part 3's `changeWords` would add " for all projects"; `PLACE_IN_TITLE` stops that);
    the Changes line `` `Removed the rules for ${name} · Kitden gateway` ``.

- [ ] **Step 1: Write the failing tests**

```python
def forget_preview(page, folder):
    return page.post("/api/changes/preview", json={"action": "gateway.forget", "params": {"folder": folder}}, headers=POST)


def test_rules_for_a_folder_no_client_lists_can_be_removed_and_undone(home):
    gone, website = str(home / "work/old-site"), project(home, "website")
    rules = {"global": {}, "projects": {
        gone: {"echo": {"tools": {"slow": "off"}}, "files": {"server": "off"}},
        website: {"echo": {"server": "on"}},
    }}
    hold(home, {"echo": echo(), "files": FILES}, rules)
    add_kitden(home, "cursor")
    path = data_dir(home) / SETTINGS_FILE
    before = path.read_bytes()
    with page_for(home) as page:
        card = page.get("/api/gateway-view").json()["gateways"][0]
        assert card["lost_rules"] == [{"path": gone, "folder": "old-site", "servers": ["echo", "files"]}]
        change = forget_preview(page, gone).json()
        assert change["after"] == [{"note": "No client lists old-site as a project now, so these rules apply in no session."}]
        assert path.read_bytes() == before
        assert page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
        assert load_settings(home)["rules"]["projects"] == {website: {"echo": {"server": "on"}}}
        assert "lost_rules" not in page.get("/api/gateway-view").json()["gateways"][0]
        assert page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
        assert path.read_bytes() == before
        assert forget_preview(page, "/nowhere").json()["detail"] == "Kitden has no rules for this folder."


def test_a_listed_project_with_a_missing_folder_keeps_its_rules(home):
    missing = str(home / "work/deleted-project")  # Claude Code still lists it; the folder is gone
    hold(home, {"echo": echo()}, {"global": {}, "projects": {missing: {"echo": {"server": "off"}}}})
    with page_for(home) as page:
        assert "lost_rules" not in page.get("/api/gateway-view").json()["gateways"][0]
        refused = forget_preview(page, missing)
    assert refused.status_code == 422
    assert refused.json()["detail"] == "This folder is a known project; its rules are in use."
```

```js
// review.test.mjs (changeWords from review.js)
test('removing the rules of a folder Kitden no longer finds names the folder', () => {
  const change = { action: 'gateway.forget', steps: [{ client: 'kitden', name: 'old-site' }] };
  const body = { action: 'gateway.forget', params: { folder: '/Users/me/work/old-site' } };
  const words = { title: 'Remove the rules for old-site', done: 'Removed the rules for old-site' };
  assert.deepEqual(changeWords(change, body), words);
  // The preview's target never adds " for all projects" to it.
  const all = { scope: 'all', project: null, others_unchanged: false };
  assert.deepEqual(changeWords({ ...change, target: all }, body), words);
});
// parts.test.mjs
test('the Changes page names the folder whose rules went', () => {
  assert.equal(changeTitle({ action: 'gateway.forget', steps: [{ client: 'kitden', name: 'old-site' }] }), 'Removed the rules for old-site · Kitden gateway');
});
```

```python
def test_the_kitden_card_lists_rules_for_folders_it_no_longer_finds():
    text = script("gateway.js")
    assert "Rules for folders Kitden no longer finds · ${" in text
    assert 'action: "gateway.forget"' in text and '"Remove…"' in text
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**. design.md's "Kitden gateway card" row gains: rules for a folder no
  client lists show in a quiet group "Rules for folders Kitden no longer finds", each with the
  folder, its servers and "Remove…" (a review with Undo).
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_gateway_access.py tests/unit/test_local_gateway_views.py tests/unit/test_page_words.py tests/security -v` and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/changes/actions.py src/kitden/local_gateway/views.py src/kitden/views/gateway_view.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/gateway.js src/kitden/web/static/js/review.js src/kitden/web/static/js/parts.js docs/design.md tests/unit/test_gateway_access.py tests/frontend/review.test.mjs tests/frontend/parts.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: remove rules for folders Kitden no longer finds"
```

---

### Task 6: Direct rows know their client columns; held rows show their clients (5.1 data, 5.2)

**Files:**
- Modify: `src/kitden/views/gateway_view.py` (each group row gains `columns`)
- Modify: `src/kitden/web/static/js/gateway.js` (new `heldClients`; `kitdenHeld(gateway, linked)`; `groupRow` uses `row.columns` for `data-clients` and its hover)
- Modify: `docs/design.md` ("Kitden gateway card" row)
- Test: `tests/unit/test_gateway_view.py`, `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `kitden.demo.build_demo_home` (the `large` sample).
- Produces:
  - Each row of `groups.move`, `groups.local`, `groups.plugin` gains `"columns": list[str]`: the
    client columns (`COLUMNS` order) of its `clients`, the Desktop Code tab counted as
    `"claude_code"` (as `connections` already counts it). `clients` keeps the real ids for the
    row's marks.
  - `export function heldClients(server, linked) -> string[]`: `linked` when `server.state !== "off"`, else `[]`.
  - A held row's chip shows the marks of `heldClients(server, linked)` with their names as its
    `aria-label` (none: the gateway mark, as today), sets `data-clients` to them, and its hover
    calls `focusRoutes(clients, { rows: false })`.

- [ ] **Step 1: Write the failing tests**

```python
def test_direct_rows_name_the_client_columns_they_reach(home):
    desktop = home / "Library/Application Support/Claude/claude_desktop_config.json"
    config = json.loads(desktop.read_text())
    config["mcpServers"]["desk"] = {"url": "https://desk.example.com/mcp"}
    desktop.write_text(json.dumps(config))
    settings = home / ".claude/settings.json"  # turn on the fixture plugin that brings md-index
    data = json.loads(settings.read_text())
    data["enabledPlugins"]["claude-md-management@claude-plugins-official"] = True
    settings.write_text(json.dumps(data))
    groups = gateway_view(build_inventory(home), [], None)["groups"]
    desk = row(groups, "move", "desk")
    assert (desk["clients"], desk["columns"]) == (["claude_desktop_code_tab"], ["claude_code"])
    assert row(groups, "plugin", "md-index")["columns"] == ["claude_code"]
    assert row(groups, "move", "Neon")["columns"] == ["cursor"]


def test_the_large_sample_gives_every_direct_row_its_columns(tmp_path):
    home = build_demo_home(tmp_path, "large")
    groups = gateway_view(build_inventory(home), [], None)["groups"]
    direct = [r for g in ("move", "local", "plugin") for r in groups[g]]
    assert len(direct) > 6  # more than the diagram draws (Task 7)
    assert all(r["columns"] and set(r["columns"]) <= {"claude_code", "codex", "cursor"} for r in direct)
```

```js
test('a held server row shows the clients that reach it here', () => {
  assert.deepEqual(heldClients({ name: 'files', state: 'on' }, ['claude_code', 'cursor']), ['claude_code', 'cursor']);
  assert.deepEqual(heldClients({ name: 'files', state: 'off' }, ['claude_code', 'cursor']), []);
  assert.deepEqual(heldClients({ name: 'files', state: 'on' }, []), []);
});
```

```python
def test_held_rows_show_their_clients_and_direct_rows_light_by_column():
    text = script("gateway.js")
    assert "heldClients(server, linked)" in text and 'row.columns.join(" ")' in text
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**. design.md "Kitden gateway card": each server row shows the marks of
  the clients that reach it through the gateway (none where it is off).
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_gateway_view.py tests/unit/test_overview.py tests/unit/test_page_words.py -v` and `node --test tests/frontend/gateway.test.mjs` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/views/gateway_view.py src/kitden/web/static/js/gateway.js docs/design.md tests/unit/test_gateway_view.py tests/frontend/gateway.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: server rows show their clients; direct rows count the Desktop tab as Claude Code"
```

---

### Task 7: The route summary draws held servers and direct routes (5.1)

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (new `cutName`, `routeLayout`; `routes(gateway, linked, direct, held)` draws from the layout; `kitdenCard` and `gatewayCard` pass every group; the "N direct" count and its click go)
- Modify: `src/kitden/web/static/style.css` (`.routes .bypass` rules go; one rule for a direct line, one for a server node)
- Modify: `docs/design.md` (Color roles paragraph; "Kitden gateway card" row)
- Test: `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 6 (`columns`, `heldClients`); `FOLD_AT = 6`; `focusRoutes(clients, { wires, rows })` (kept as it is); gateway.js's own `opens(node, label, open)` (gains `role = "link"`; not the `opens()` of `parts.js`).
- Produces:
  - `export function cutName(name, max = 24) -> string`: longer names end in "…" at `max` characters.
  - `export function routeLayout({ name, linked, held, direct }, cap = FOLD_AT) -> { width: 640, height, nodes }`.
    `held`: Kitden held rows (`{ name, kind, state }`); `direct`: group rows (`{ name, columns }`),
    in group order (move, local, plugin). `nodes` is the Tab order, each
    `{ key, kind: "client" | "hub" | "held" | "direct" | "more", y, text, sub, label, clients }`:
    the three clients (`client:<id>`), `hub`, the first `cap` held (`held:<name>`, sub "Local" or
    "Remote", plus " · Off" when off), `held:more`, the first `cap` direct (`direct:<i>`, sub
    "Direct", `clients` = its `columns`), `direct:more` (text `` `+${n} more` ``). Labels carry the
    whole name: client `` `${client}: connected to ${name}` `` or `not connected to`; hub
    `` `${name}: ${plural(n, "client", "clients")}` ``; held `` `${server} in ${name}` `` (`, off here`); direct
    `` `${server}: Direct from ${joinWords(client names)}` ``; more `` `${n} more in the list below` ``.
  - Placement (the numbers the tests do not fix): width 640; clients at x 8–200 as today; hub
    140 wide at x 250; servers 192 wide at x 440; right-column rows 36 px apart from y 24, a 12 px
    gap between the held and direct groups; height = max(150, last row + 26); the three clients
    centred on the height. Lines: a wire per linked client to the hub (accent, as today), a wire
    from the hub to each held server that is on, and one thin neutral line from each client in a
    direct node's `clients` to that node. Lines are drawn first, under every node; each draws
    once (`drawn` keys `${gateway.id}:${kind}:${key}`, delay `min(order × 90, 450)` ms) and rests.
    A direct line sits in its client's `.route` group, so `focusRoutes` lights it.
  - Keyboard: DOM order is `nodes` order; every node has `tabindex="0"` and its `label`.
    Client with an app: opens it (as today); without: role "button", Enter → `showDirect(client)`.
    Hub: opens the gateway's page when it has one, else role "img" (its focus lights every route).
    Held node: what that row's "Details" does (`showKitdenServer(server)`). Direct node:
    `showServer(row.name)`. More node: focuses and scrolls to the list below ("In the gateway"
    heading for held, "MCP servers not in the gateway" for direct; give them `tabindex="-1"`).
    Hover or focus on a held or direct node calls `focusRoutes(node.clients, { rows: false })`.

- [ ] **Step 1: Write the failing tests**

```js
const { cutName, heldClients, routeLayout } = await import('../../src/kitden/web/static/js/gateway.js');
const held = (n) => Array.from({ length: n }, (_, i) => ({ name: `held-${i}`, kind: 'local', state: 'on' }));
const direct = (n) => Array.from({ length: n }, (_, i) => ({ name: `direct-${i}`, columns: ['cursor'] }));
const layout = (h, d, linked = []) => routeLayout({ name: 'Kitden gateway', linked, held: h, direct: d });

test('the diagram puts every node in one keyboard order with a name each', () => {
  const l = layout([{ name: 'files', kind: 'local', state: 'on' }, { name: 'docs', kind: 'remote', state: 'off' }], [{ name: 'Neon', columns: ['codex', 'cursor'] }], ['claude_code']);
  assert.deepEqual(l.nodes.map((n) => n.key), ['client:claude_code', 'client:codex', 'client:cursor', 'hub', 'held:files', 'held:docs', 'direct:0']);
  assert.ok(l.nodes.every((n) => n.label));
  const neon = l.nodes.find((n) => n.key === 'direct:0');
  assert.deepEqual([neon.text, neon.sub, neon.clients, neon.label], ['Neon', 'Direct', ['codex', 'cursor'], 'Neon: Direct from Codex and Cursor']);
  assert.equal(l.nodes.find((n) => n.key === 'held:docs').sub, 'Remote · Off');
});

test('a Desktop Code tab entry is a direct route of Claude Code', () => {
  const l = layout([], [{ name: 'desk', clients: ['claude_desktop_code_tab'], columns: ['claude_code'] }]);
  assert.deepEqual(l.nodes.find((n) => n.kind === 'direct').clients, ['claude_code']);
});

test('the diagram grows with its servers, then stops at six of each with +N more', () => {
  assert.ok(layout(held(2), []).height < layout(held(4), direct(3)).height);
  const big = layout(held(40), direct(30));
  assert.equal(big.nodes.filter((n) => n.kind === 'held').length, 6);
  assert.equal(big.nodes.filter((n) => n.kind === 'direct').length, 6);
  assert.deepEqual(big.nodes.filter((n) => n.kind === 'more').map((n) => n.text), ['+34 more', '+24 more']);
  assert.equal(big.height, layout(held(7), direct(7)).height);
  const right = big.nodes.filter((n) => !['client', 'hub'].includes(n.kind)).map((n) => n.y);
  assert.equal(new Set(right).size, right.length);
  assert.ok(big.nodes.every((n) => n.y > 0 && n.y < big.height));
});

test('a long server name is cut with … and keeps its whole name in its label', () => {
  const name = 'a-very-long-server-name-from-the-large-sample-0001';
  assert.equal(cutName(name).length, 24);
  assert.ok(cutName(name).endsWith('…'));
  assert.equal(cutName('files'), 'files');
  const node = layout([], [{ name, columns: ['codex'] }]).nodes.find((n) => n.kind === 'direct');
  assert.equal(node.text, cutName(name));
  assert.ok(node.label.startsWith(name));
});
```

```python
def test_the_route_summary_draws_direct_routes_quietly():
    text = script("gateway.js")
    assert '"Direct"' in text and "more in the list below" in text
    assert "${around} direct" not in text and "bypass" not in text  # the amber count is gone
    assert not any(".routes" in line and "--lamp-warn" in line for line in CSS.splitlines())
    words = "The gateway controls only the servers in it. Direct entries and terminal tools are outside it."
    assert words in text
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement** `cutName` and `routeLayout`, then rewrite `routes()` to draw from
  them. `kitdenCard`: `routes(gateway, linked, [...groups.move, ...groups.local, ...groups.plugin], gateway.servers || [])`;
  `gatewayCard`: the same groups and no held servers (its held list is read live below).
  design.md: the Color roles paragraph adds "A direct route is a thin neutral line with the
  word Direct, never amber: direct is not a fault."; the card row describes the diagram (clients
  left, the gateway in the middle, its servers right with a wire each, each direct server below
  with a line from each client that has it, six of each then "+N more", every node reachable by
  Tab, lines draw once and rest).
- [ ] **Step 4: Run** `node --test tests/frontend/*.test.mjs` and `uv run pytest tests/unit/test_page_words.py -v` → PASS (`test_gateway_wires_do_not_fake_traffic` included).
- [ ] **Step 5: Look at it.** `kitden demo --size medium`, then `--size large`: the Gateway page
  in light and dark, at 1280 px and 600 px wide, with reduced motion on; Tab through every node
  (focus ring visible, the label is read); no name runs past its node; nothing moves while idle.
  Fix what you see before committing.
- [ ] **Step 6: Run all checks**, then commit

```bash
git add src/kitden/web/static/js/gateway.js src/kitden/web/static/style.css docs/design.md tests/frontend/gateway.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: the diagram draws held servers and each direct route"
```

---

### Task 8: README, roadmap and a last look at design.md for Part 5

**Files:**
- Modify: `README.md` ("Use one gateway for every client", "The Kitden gateway: tools per project")
- Modify: `docs/development.md` (the hand check's step 5 quotes the Strict switch: "Strict: only tools you turned on" → "Strict: only tools that are on")
- Modify: `ROADMAP.md` (only when the owner's edit is committed; see below)
- Modify: `docs/design.md` (only if the read-through below finds a gap)
- Test: `tests/unit/test_docs_words.py`

- [ ] **Step 1: Write the failing test**

```python
def test_readme_says_what_a_switch_cannot_stop_and_what_a_new_tool_says():
    readme = " ".join((ROOT / "README.md").read_text().split())
    for words in ("a call already running is not stopped", '"New · waits"', '"Not sure"', "Direct"):
        assert words in readme, words
    assert '"New · off"' not in readme
    assert "tools you turned on" not in readme
    assert "tools you turned on" not in (ROOT / "docs/development.md").read_text()
```

- [ ] **Step 2: Run it to see it fail**: `uv run pytest tests/unit/test_docs_words.py -v`.
- [ ] **Step 3: Update README**, short and plain: the diagram shows the servers in the gateway
  and each direct route, labelled Direct; a server row shows its clients; each tool says where
  its state comes from ("All projects", "This project", "From <folder>", "On by default",
  "New · waits") and "Use <project>" takes away a project's own rule; a tool turned off is
  refused at once, and a call already running is not stopped; strict mode names the tools it
  keeps on and a new tool waits as "New · waits"; "Turn off every writing tool…" is a checklist,
  with tools Kitden is not sure about under "Not sure"; each tool row shows "12 calls · last
  today 14:02" (replaces the hover sentence); rules for folders Kitden no longer finds can be
  removed. The strict paragraph changes its two old phrases: turn on "Strict: only tools that
  are on"; "the server offers only the tools that are on" (strict turns the known tools on for
  you), and a tool it adds later waits as "New · waits". Keep "In a folder Kitden does not know
  as a project, the All projects switches apply." (pinned). In `docs/development.md`, the hand
  check quotes "Strict: only tools that are on".
- [ ] **Step 4: Read design.md's Gateway rows against the page** (Tasks 2, 4–7 each changed one);
  fix any word that no longer matches the code.
- [ ] **Step 5: ROADMAP.** Run `git status --short ROADMAP.md`. If it shows `M` and this part did
  not make it, do not touch it: put these lines in the report instead. Otherwise move this part's
  line from "## Planned" (if there is one) to "### Not released yet" as:
  `- **Access shows routes and origins:** the Gateway diagram draws the servers in the gateway and each direct route (plugins and the Claude Desktop Code tab count); server rows show their clients; each tool says where its state comes from; the writing tools review is a checklist with "Not sure"; strict mode names the tools it keeps on; rules for folders Kitden no longer finds can be removed; call counts show on the row.`
  and change, in the same section, "a server can offer only the tools you turned on" to "a
  server can offer only the tools that are on", 'wait as "New · off"' to 'wait as "New · waits"',
  '"Turn off every writing tool…" is one review' to '"Turn off every writing tool…" is a
  checklist', and "**Calls counted:** hover a tool to see how often it was called and when
  last." to "**Calls counted:** each tool row shows how often it was called and when last."
- [ ] **Step 6: Run all checks**, then commit (add `ROADMAP.md` only if Step 5 changed it)

```bash
git add README.md docs/development.md tests/unit/test_docs_words.py
git commit -m "Docs: Access shows routes, origins and honest limits"
```

---

## Builder calls (decisions the spec does not settle)

- Builder call: a strict tool without a rule is always `new` in today's data (the same test in `tools_view`), so the word is always "New · waits"; "Waits" alone never shows and the separate "New" flag goes.
- Builder call: a tool of a server that is off rests off with "Server off" in place of its origin, its switch cannot be pressed, and the writing batch is not offered.
- Builder call: the "Whole server" row shows an origin word too.
- Builder call: "Differs from …" stays only when the project's rule changes the state; "Use …" shows whenever the project has its own rule.
- Builder call: the running-call sentence lives in `AT_ONCE`, so the single switch says it too.
- Builder call: "Keeps on" lists every known tool not off for all projects; a move's strict line keeps its words.
- Builder call: the checklist lists tools on in the scope whose hint is not "reads"; the button still shows only when a writing tool is on.
- Builder call: the checklist is its own `checklist` field and `checklistSection`, beside Add missing's, because Part 4 reshapes `alignSection`.
- Builder call: one Remove per folder removes all its rules in one settings step, as action `gateway.forget`; the group sits on the Kitden card; the full path is hover text only.
- Builder call: the diagram draws the first six held and six direct servers (`FOLD_AT`), then "+N more" nodes that focus the list below; names are cut at 24 characters.
- Builder call: a direct route is a thin neutral solid line that draws once; the word "Direct" sits once on each direct server node, not on every line.
- Builder call: a node without its own action (the Kitden hub, a client without its app) is still focusable and lights its routes; such a client's Enter goes to its first direct row.
- Builder call: a registered gateway's card draws the same direct routes; its held servers stay in the list below, read live.
- Builder call: the wire stagger stops at 450 ms so the total stays under 500 ms.
- Builder call: the Strict switch's `aria-label` (and the docs that quote it) follows the row's new words: "Strict: only tools that are on".
