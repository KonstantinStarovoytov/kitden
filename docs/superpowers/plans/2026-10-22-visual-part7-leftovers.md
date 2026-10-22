# Part 7: Leftovers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix what the owner's second walkthrough found, then fix or close every minor finding
that the reviews of the earlier Parts 1–6 deferred, each with a test or a one-line reason.

**Architecture:** No new feature. Task 1 holds the walkthrough fixes the controller rules on.
Tasks 2–9 each fix one area of the deferred list: what clients read, the live page, writes to
`~/.claude.json`, the "loads twice" rule, the Keychain, the gateway, the page, and small items.
Task 10 updates the docs. The triage table below says, for every deferred item, whether it is
fixed here, already fixed, settled by another part, or closed with a reason.

**Tech Stack:** Python 3.13, Starlette, MCP SDK 2.3, watchfiles; plain ES modules, one CSS
file; pytest on sandbox homes and the Part 1 samples; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 7 (and 6.5 for
the map rule), built on `docs/research/visual-management-ux-concept-2026-10-22.md` (§12: keep
the map only if it helps). Master plan: `docs/superpowers/plans/2026-10-22-visual-management.md`
(its Rules and "Names that cross part boundaries" bind this plan). The raw deferred list is kept
with the plan, outside the repository.

## Global Constraints

- `AGENTS.md` in full: code, comments, UI text and docs in simple English; Russian with the
  owner; the checks before each commit; dated facts about other tools; short plain commit
  subjects (one to three lines, no prefix, ending with the co-author line the session gives).
- Every write to a client's settings goes through `src/kitden/changes/engine.py`: preview →
  Apply with a backup → verify → Undo. No task writes a client file any other way.
- Main pages show a name, the client, a state and an action; paths, addresses and commands stay
  in Details.
- `docs/design.md` changes in the same commit as the page change it describes; a changed or new
  page word is pinned in `tests/unit/test_page_words.py` in that commit.
- A fact about another tool is checked against that tool's current docs before it is built, with
  `checked 2026-10-22` (or the day of the check) next to it. What the docs do not confirm is
  written as "not checked" and not built.
- Tests use `make_home(...)` / `write_cursor_fixture_state(home)` or `build_demo_home(root, size)`
  (Part 1). No real `claude`, `codex`, `cursor` or `security`, no real Keychain, no network, never
  the real home folder.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`,
  `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`. Stage files by
  name; never `git add -A`, `git add .` or `git commit -a`.
- `ROADMAP.md`: while `git status` shows it modified and not by this part, no task edits or
  stages it; Task 10 writes the lines into the part's report instead.
- Check first: each task starts by checking its items against `main` (after Parts 1–6). An item
  that is already fixed is closed with one line in the report. An item the triage marks
  "superseded by Part N" that Part N did not settle moves into Task 9 with a test.
- Line numbers are hints; find code by name. Part 3 splits `panel.js` into `panel.js` (shell and
  re-exports), `details.js`, `tools.js` and `review.js`; each task below names the module that
  defines the function (`heldActions` and `offerLabel` in `details.js`, `callsText` in
  `tools.js`). New node tests go in that module's test file (`details.test.mjs`,
  `tools.test.mjs`, `review.test.mjs`); existing tests in `panel.test.mjs` are edited where they
  are.

## Review Focus

1. Claude Code rewrites `~/.claude.json` between Kitden's direct write and its check: the change
   is verified and Claude Code's update is kept; a later failure takes back only Kitden's entry
   (Task 4 `test_a_direct_write_keeps_an_update_claude_code_makes_meanwhile`,
   `test_a_failed_change_takes_back_only_its_entry_in_claude_json`).
2. The rules file breaks after a tool was turned off in an open session: the tool stays refused,
   the others still work (Task 7
   `test_a_tool_turned_off_stays_refused_when_the_rules_file_then_breaks`).
3. A token that ends in a line break, or holds a non-ASCII letter, moves into the Keychain and
   the server gets it back unchanged (Task 6
   `test_a_token_with_a_line_break_moves_and_comes_back_unchanged`).
4. An MCP entry with an unclosed `${` or other text inside `${…}` that may be a token is copied
   to another client: the refusal never shows that text (Task 9
   `test_a_refusal_never_shows_text_that_is_not_a_variable_name`).
5. Ctrl+C while Cursor's version command runs (it starts Electron, up to 20 s): the page stops
   within a few seconds (Task 8 `test_stopping_the_page_does_not_wait_for_a_version_command`).

## Triage of the deferred findings

Sources: the ledgers of the earlier review follow-up, Parts 1–6 (F1 truth, F2 gateway contract,
F3 management, F4 speed, F5 secrets, F6 instructions), checked against the code on 2026-10-22
(`align-listing-fix`, one commit ahead of `main`), plus one item the coordinator added (47).
Lines in the raw list that are tool-call noise are left out.

| # | Item (source) | Status | Reason |
| --- | --- | --- | --- |
| 1 | ROADMAP part-1 line got "(done)" early (F1) | already fixed | No "(done)" in `ROADMAP.md`. |
| 2 | Unreachable "Nothing in it yet." in `gatewayCardWords` (F1) | fix here, Task 8 | The card exists only with servers, clients or a problem. |
| 3 | With `problem` set, the card line hides servers and clients (F1) | fix here, Task 8 | `line = gateway.problem \|\| …`. |
| 4 | No node test for no action / an old entry; no route test that `/api/overview` passes `held` and `problem` (F1) | fix here, Task 8 | Tests only. |
| 5 | Scope line on tabs with no "+ Add" (F1) | already fixed | `scopeLine` checks `hasAdds(kind)`. |
| 6a | Page-words test checks only the literal (F1) | won't fix | Page-words tests pin words by design; behaviour is in node tests. |
| 6b | `library.test.mjs` shadows `row` (F1) | fix here, Task 9 | Two local `const row` in test bodies. |
| 7 | `via_gateway == KITDEN_GATEWAY` guard no test makes fail (F1) | won't fix | A cheap guard; held items carry owner `kitden` today. |
| 8a | No test for a plugin-provided `kitden` entry in findings (F1) | fix here, Task 9 | Test only. |
| 8b | Test file imports `make_home` directly (F1) | won't fix | 43 test files import from `tests.conftest`; it is the repo's pattern. |
| 9a | A held, unchanged remote server is asked by `needs_sign_in` at preview (F1) | won't fix | One request to that server's own address on a rare path; skipping it needs the Keychain read first. |
| 9b | `after.py` loop coupled to `edit.key[0]` (F1) | won't fix | No behaviour change. |
| 9c | `test_after` imports helpers from `test_local_gateway_move` (F1) | won't fix | Same pattern as `test_add_server`. |
| 10a | No way to fold back after "Show all" (F1) | fix here, Task 8 | Spec: "a folded group can fold back". |
| 10b | Fold focus test only greps strings (F1) | won't fix | Focus wiring is DOM code; `visibleRows` has a node test and Task 8 adds one. |
| 10c | ROADMAP gateway line packs two items (F1) | superseded by Part 8 | v0.3.0 notes rewrite these lines; ROADMAP is the owner's for now. |
| 11 | Focus row index 6 hard-coded (F1) | already fixed | `i === FOLD_AT`. |
| 12 | `allowed_tools` calls `strict_mode` per tool (F2) | won't fix | A dict lookup per tool. |
| 13a | Strict row words per client untested; row text not pinned (F2) | superseded by Part 5 | Part 5 Task 2 rewrites and pins the Strict row. |
| 13b | `strict=True` in a move relies on app.py's tool read (F2) | won't fix | app.py's preview is the only caller and refuses first. |
| 14a | `views.py` imports private `_scopes` (F2) | superseded by Part 5 | Part 5 Task 1 rewrites `_states` and `tools_view`. |
| 14b | All-projects view: a tool ruled only in a project shows New (F2) | superseded by Part 5 | 5.3 origin words: "New · waits" is true for all projects. |
| 15 | A server removed from gateway.json mid-session stays callable (F2) | already fixed | `is_allowed` refuses a server not in the file. |
| 16 | `list_changed` can be a no-op nudge (F2) | won't fix | Best effort by design; keeping it waits for a real-client check (earlier design, "Left to the builder"). |
| 17 | A tool turned off mid-session is allowed again when the file then breaks (F2) | fix here, Task 7 | Fallback is the start rules. |
| 18a | `tool_hint` computed twice per tool (F2) | already fixed | One call in `tools_view`. |
| 18b | Changes line of a batch drops on/off and gets long (F2) | fix here, Task 7 | `changeTitle` lists every tool name. |
| 18c | With state "on" (API only) the batch note says "refused at once" (F2) | won't fix | The sentence says what a switch does and when the list updates; the page offers only "off". |
| 19 | `destructiveHint: false` alone gives "unknown" (F2) | already fixed | `tool_hint`: any hint key means "writes"; Part 5 lists unknown tools under "Not sure". |
| 20a | `callsText` shows `NaN:NaN` on a broken `last` (F2) | fix here, Task 7 | On Part 5's `callsText`. |
| 20b | A test sets `TZ=UTC` and never restores it (F2) | fix here, Task 7 | — |
| 20c | `count_call` chmods the folder on every call (F2) | won't fix | One cheap call keeps the folder private. |
| 20d | Forwarded calls that errored are counted (F2) | won't fix | The count is of forwarded calls, as `docs/development.md` says. |
| 21a | Long lines in README (F2) | superseded by Part 8 | README is rewritten. |
| 21b | Long lines in `docs/development.md` (F2) | fix here, Task 10 | — |
| 22a | Unguarded put-back in Undo after a reinstall (F3) | already fixed | `_put_entry_back` errors end in `UNDO_BLOCKED`. |
| 22b | `IMPORT_HINT` could mention removal (F3) | won't fix | Turning off is enough and undoable; Details offers Remove where it can. |
| 22c | Duplicate fix text where Remove is not offered (F3) | won't fix | The text says what to do by hand; the button shows only where an offer matches (`footerActions`). |
| 22d | `NOT_INSTALLED` matches by suffix (F3) | won't fix | A marketplace name holds no "@", so the suffix is the marketplace. |
| 22e | Project-scope plugin remove: Apply and Undo tested only at preview (F3) | fix here, Task 9 | Test only. |
| 23a | Undo copy and digest errors end as a 500 (F3) | fix here, Task 4 | `remove_folder`, `copy_folder` and the read-back are not caught in `undo`. |
| 23b | `offerLabel` twin counting untested (F3) | fix here, Task 9 | Node test only. |
| 23c | Duplicate flags carry `skill.remove` where no copy can go (F3) | won't fix | As 22c. |
| 24 | A change not fully put back ends `RESTORED` (F3) | already fixed | Part 3 ruling: neutral line; the error names what was not put back. |
| 25a | Put back's "twice" note reads only the all-projects rule (F3) | fix here, Task 7 | `state_in(settings, [], …)`. |
| 25b | Remove note ignores registered gateways (F3) | already fixed | `_gateway_remove_words` names them. |
| 25c | "Put back in X…" offered to a client that has the name (F3) | fix here, Task 7 | Preview refuses it ("X already has …"). |
| 25d | An entry with both `command` and `url` is accepted (F3) | fix here, Task 9 | Claude Code gets `type: http` with a command. |
| 25e | A project-folder placeholder is refused with the shell reason (F3) | already fixed | Refused as "cannot fill in the project folder". |
| 25f | `heldButtons` / `writableClients` untested (F3) | fix here, Task 7 | Covered by the `putBackClients` test. |
| 26a | Secret note overstates for harmless env values (F3) | won't fix | Kitden cannot tell a harmless value from a secret; saying it when unsure is the safe side. |
| 26b | "+ Add" on cells that preview refuses (F3) | superseded by Part 2 | 2.3: no "+ Add" where preview would refuse. |
| 26c | Codex `Authorization` header matched case-sensitively (F3) | fix here, Task 9 | `authorization: Bearer ${X}` is refused instead of translated. |
| 26d | `bearer_token_env_var` silently wins over an `Authorization` header (F3) | fix here, Task 9 | Refused. |
| 27a | An unclosed `${…` can echo text in a refusal (F3) | fix here, Task 9 | Checked: `${tok-SENTINEL…` is shown in the sentence. |
| 27b | A Codex literal `${X}` kept for Cursor gets no secret note (F3) | won't fix | Rare; the note follows `redact`, which reads `${X}` as a reference. |
| 28a | `addChoices` ignores its arguments (F3) | fix here, Task 9 | — |
| 28b | A project plugin install makes other projects' cells say "has it in another project" (F3) | won't fix | True words; the cell offers no Add that would fail. |
| 28c | Cursor's via and done cells also get the per-project hint (F3) | won't fix | The hint still tells how to add it to one project in Cursor; `test_cursor_plugin_cells_say_where_to_add_per_project` pins it on purpose. |
| 29a | "Not the same; not touched" beside an add of that name to a third client (F3) | superseded by Part 4 | 4.3 "Needs your decision". |
| 29b | Stale file changes stay visible under a disabled Apply (F3) | superseded by Part 4 | 4.3 rebuilds the Add missing review. |
| 29c | The toast count includes deduplicated items (F3) | superseded by Part 4 | 4.3 "Adds N items to <project>" sets the count. |
| 30a | No test that Add missing with Cursor importing puts a Claude Code plugin in the project and does not name Cursor (F3) | fix here, Task 5 | Test only. |
| 30b | Cursor's import note does not check Cursor already loads the plugin (F3) | fix here, Task 5 | `plugin.install` adds `CURSOR_IMPORT` without a check. |
| 31a | `fake_binary` duplicates `fake_client_command` (F4) | already fixed | No `fake_binary` left. |
| 31b | `version_cache.CLIENTS` repeats `versions._COMMANDS` keys (F4) | won't fix | Three names; no behaviour. |
| 31c | First-scan timing bound `< 1` s is tight (F4) | fix here, Task 9 | `test_the_first_scan_runs_no_version_command`. |
| 31d | `_read_version` reads the file twice per Codex scan (F4) | won't fix | One small JSON file. |
| 32a | Ctrl+C can wait for a running version command (F4) | fix here, Task 8 | Spec item. |
| 32b–e | No refresh with `first_scan_later=False`; plain path ends progress late; duplicated client mapping; one error line for refresh and rescan (F4) | won't fix | Test-only paths and log lines; the page keeps working. |
| 33 | `versions.json` missing from the data-file list (F4) | fix here, Task 10 | — |
| 34a | README "under a second" rests on in-process numbers (F4) | superseded by Part 8 | README is rewritten. |
| 34b | A fake `sleep` can outlive the script on a failure path (F4) | won't fix | Failure path; ends by itself. |
| 34c | Script uses `uvicorn.Server`, not `run_server` (F4) | won't fix | The script runs the server in its own thread. |
| 34d | `HOME` restored to `""` when it was unset (F4) | fix here, Task 9 | If Part 1's move of the generator left it. |
| 34e | Start numbers in two places (F4) | superseded by Part 8 | v0.3.0 notes. |
| 35a | Keychain reads can overrun the start timeout (F5) | won't fix | An unlock prompt may take time; it delays only that server. |
| 35b | A refused account name says "could not reach" (F5) | fix here, Task 6 | — |
| 35c | A reference without "/" gives a broken sentence (F5) | fix here, Task 6 | "a secret of  from the Keychain". |
| 35d | `Runner` type is loose (F5) | won't fix | Typing only. |
| 35e | `KITDEN_SECURITY` honoured in production (F5) | already fixed | Commented and documented as a test hook. |
| 35f | The guard does not reach non-SDK children (F5) | already fixed | Every child inherits `KITDEN_SECURITY` pointing at a missing path. |
| 35g | The fake prints values raw (F5) | won't fix | It does what `security -w` does. |
| 36a | Restore says "The original settings were restored." when an item kept its new value (F5) | already fixed | That item goes to `lost`, so the sentence is not said. |
| 36b | A name with `"` or `\` is refused only at Apply, with "could not reach" (F5) | fix here, Task 6 | — |
| 37a | Undo deletes items before inverse commands (F5) | already fixed | Created items are deleted last. |
| 37b | A gateway step's record holds plain old values (F5) | won't fix | Said by "This change's backup or record holds a secret." |
| 37c | `_server_step` key filter matches either field (F5) | won't fix | A local server has env and a remote one headers; one key in both is not a real case. |
| 37d | `_server_step` treats an unreachable Keychain as a missing item (F5) | won't fix | Apply then stops with "could not reach the Keychain" and restores. |
| 38a | `held_servers` and `keychain_steps` call `secrets_out` for a boolean (F5) | won't fix | No behaviour. |
| 38b | A test relies on newest-first order without a comment (F5) | won't fix | — |
| 39a | No size cap when scanning removed folders for secrets (F5) | won't fix | A cap could miss a secret; skill folders are small. |
| 39b | Simple `.env` parser (F5) | won't fix | It errs toward "holds a secret". |
| 40a | `docs/development.md` Gateways line overlong (F5) | fix here, Task 10 | — |
| 40b | README does not name "Move secrets to the Keychain…" (F5) | superseded by Part 8 | — |
| 41 | An item whose own write failed is said to "keep the new value" (F5, parked) | fix here, Task 6 | "may hold the new value". |
| 42 | A token that ends in a line break never reads back equal (F5, parked) | fix here, Task 6 | — |
| 43 | ROADMAP's Part 5 line says OAuth servers move (F5 note) | fix here, Task 10 | A line for the owner (ROADMAP is the owner's). |
| 44 | Cursor `.cursor/agents`, `.claude/agents`, `.cursor/commands`, CLAUDE.md; Claude Code AGENTS.md without CLAUDE.md; agent names from `name:` (F6) | fix here, Task 2 | Built only where the docs confirm. |
| 45a | Overview does not count instruction files (F6) | already fixed | `LOAD_KINDS` has instructions. |
| 45b | Two files fail `ruff format --check` (F6) | already fixed | `82fefdc`. |
| 45c | Visual check of the page on a fixture home (F6) | superseded by walkthrough 2 | The owner walks the page in `kitden demo`. |
| 46 | The watcher does not watch project folders (F6) | fix here, Task 3 | Spec item. |
| 47 | The review's After chips for turning a Claude Code user plugin on or off do not name Cursor (coordinator) | fix here, Task 5 | `cursor.py _claude_plugins` reads `enabledPlugins`; app.py's comment says only add and remove reach Cursor. |

Spec items with no line above: safer `~/.claude.json` writes (Task 4), one start read (Task 8),
the gateway card's set-up for every client (Task 8), `tests/fixtures/README.md` (Task 9).

---

### Task 1: Walkthrough 2 fixes (the controller fills this task)

**Files:** set by each ruling. For the map rule: `src/kitden/web/static/js/store.js`
(`MAP_SWITCH`, `overviewMode`), `src/kitden/web/static/js/overview.js` (the switch),
`src/kitden/web/static/js/details.js` (`contextLinks`, which draws "Show on the map" since Part 6),
`docs/design.md`, `tests/frontend/store.test.mjs`, `tests/frontend/details.test.mjs`,
`tests/unit/test_page_words.py`.

**Interfaces:**
- Consumes: the results file `docs/research/walkthrough-<date>.md` (Part 6's script, the owner's
  answers); Part 6's map names (`map.js`, local storage key `kitden.overview`, `overviewMode()`
  and `setOverviewMode(mode)` in `store.js`, the List | Map switch in `overview.js`); Part 6's
  "Show on the map" entry in `contextLinks(row, definitions, view)` (`details.js`).
- Produces (map rule only): `export const MAP_SWITCH: boolean` in `store.js`, beside
  `OVERVIEW_KEY`, so `overviewMode()` and `reload()` (which reads `/api/setup-map` only while
  `overviewMode()` is `"map"`) see it without importing a page module. Part 8's `mapOffered()`
  returns it.

The controller turns each finding of the second walkthrough into a ruling in the part's ledger
before this task starts: the finding, the change, where it lives, and the test that pins it. A
finding that needs a spec change, not a fix, goes to the owner instead. If the owner skipped the
walkthrough, the ledger says "Walkthrough 2: skipped" and this task is empty.

- [ ] **Step 1: For each ruling, write the failing test first**: a node test for a page helper, a
  `test_page_words.py` pin for a word, a pytest for data. Run it and see it fail.
- [ ] **Step 2: Make the fix**; when it changes the page, `docs/design.md` in the same commit.
- [ ] **Step 3: Run all checks**, then commit that finding alone (one commit per finding):

```bash
git add <the files of this finding>
git commit -m "Walkthrough: <the finding in a few words>"
```

- [ ] **Step 4 (only if the owner found the map does not help, spec 6.5): hide the map.** The
  code stays. Tests first:

```js
// tests/frontend/store.test.mjs (import MAP_SWITCH, overviewMode, setOverviewMode from store.js)
test('with the map switch off the Overview is the list, whatever was chosen before', () => {
  globalThis.localStorage = { getItem: (key) => (key === 'kitden.overview' ? 'map' : null), setItem() {} };
  assert.equal(MAP_SWITCH, false);
  assert.equal(overviewMode(), 'list');
  setOverviewMode('map');
  assert.equal(overviewMode(), 'list');
});
// tests/frontend/details.test.mjs: in Part 6's 'Show on the map comes last, except on the map
// itself', no list ends with 'Show on the map' while MAP_SWITCH is false.
```

```python
def test_the_map_is_hidden_behind_one_switch():
    assert "export const MAP_SWITCH = false" in script("store.js")
    assert "MAP_SWITCH" in script("overview.js") and "MAP_SWITCH" in script("details.js")
```

  Implement: `overviewMode()` answers `"list"` while `MAP_SWITCH` is false, so `reload()` never
  reads `/api/setup-map`; `overview.js` draws the List | Map switch only when `MAP_SWITCH`;
  `contextLinks` leaves out "Show on the map"; an address that selects a map item opens the list
  with that selection; `/api/setup-map` and its tests stay. `docs/design.md`: the map row says the
  map is hidden behind `MAP_SWITCH` after walkthrough 2. The part's report tells Part 8: "skip the
  map stop (spec 6.5); `mapOffered()` returns `MAP_SWITCH`".
  Commit: `Overview: hide the map switch after the walkthrough`.

---

### Task 2: What clients read: agents and AGENTS.md (picture gaps)

**Files:**
- Modify: `src/kitden/clients/base.py` (gains `front_matter`, moved from `views/skills.py`, and
  `agent_items`), `src/kitden/views/skills.py` (imports `front_matter` back from `base.py`),
  `src/kitden/clients/claude_code.py` (`_instruction_files`, `_project_files`),
  `src/kitden/clients/cursor.py` (user and project scan), `src/kitden/views/explain.py` (`reads`)
- Create fixtures: `tests/fixtures/claude_code/2.1.283/home/.claude/agents/team/lead-file.md`
  (`name: lead`, `description: Leads`), `.../home/.claude/agents/notes.md` (no front matter),
  `tests/fixtures/cursor/3.21.16/home/.cursor/agents/planner.md` (no `name`),
  `tests/fixtures/cursor/3.21.16/home/work/site/.cursor/agents/tester.md` (`name: site-tester`)
- Test: `tests/unit/test_read_claude_code.py`, `tests/unit/test_read_cursor.py`,
  `tests/unit/test_explain.py`, `tests/unit/test_library.py` (instruction rows that count every item)

**Interfaces:**
- Produces: `front_matter(path: Path) -> dict[str, str]` in `clients/base.py` (same behaviour as
  today's `views/skills.py front_matter`; `views/skills.py` re-exports it).
  `agent_items(client: str, folder: Path, scope: Scope, owner: str, project: str | None = None, *, recursive: bool, needs_name: bool, kind: SourceKind = SourceKind.FILE) -> list[Item]`:
  one `ItemKind.INSTRUCTIONS` item per `*.md` agent file, category `agent`, named by its `name:`
  front matter; with `needs_name` a file without `name` or `description` is skipped, else it is
  named by its file stem.

- [ ] **Step 1: Check the docs and write the dates.** First look on 2026-10-22 (check again; build
  only what the docs say on the day):
  - cursor.com/docs/context/subagents: Cursor reads agents from `.cursor/agents/`, `.claude/agents/`
    and `.codex/agents/` in a project and in the home folder; Markdown with YAML front matter;
    `name` is optional and defaults to the file name. Also check whether the `.claude` and
    `.codex` folders follow "Include Third-Party Plugins" as `.claude/skills` does
    (`CursorAdapter` reads that folder only when it is on): if the docs say so, read them only
    then; if they do not, read them always and write "not checked" for the setting.
  - cursor.com/docs/context/commands: lists no commands folder (it describes a move to skills).
    If that holds, `.cursor/commands` is "not checked" and not built.
  - cursor.com/docs/context/rules: AGENTS.md at the root and in sub-folders; CLAUDE.md is not
    named. If that holds, Cursor and CLAUDE.md is "not checked" and not built.
  - code.claude.com/docs/en/memory (section "AGENTS.md"): from v2.1.277, Claude Code reads
    `AGENTS.md` and `.claude/AGENTS.md` when there is no `CLAUDE.md`, `.claude/CLAUDE.md` or
    `CLAUDE.local.md` in the folder (`~/.claude/CLAUDE.md` does not count); the setting
    `pluginConfigs["cc-plugin-agents-md@builtin"].options.instructionFiles` (before v2.1.285 the id
    `agents-md@builtin`) in `~/.claude/settings.json` may be `claude-md-and-agents-md` (both) or
    `managed-only` (neither).
  - code.claude.com/docs/en/sub-agents: `name` and `description` are required; a file without
    `name` is skipped; the name comes only from `name:`, not the file or its sub-folder.

- [ ] **Step 2: Write the failing tests**

```python
def test_claude_code_names_an_agent_by_its_name_field_and_skips_one_without(tmp_path, no_version):
    home = make_home(tmp_path, "claude_code/2.1.283")
    agents = {i.name for i in ClaudeCodeAdapter(home).scan().items
              if i.kind is ItemKind.INSTRUCTIONS and dict(i.summary)["category"] == "agent"}
    assert agents == {"reviewer", "lead"}  # not "team:lead-file"; notes.md has no name


def test_claude_code_reads_agents_md_only_where_the_project_has_no_claude_md(tmp_path, no_version):
    # a known project with only AGENTS.md gets a Claude Code item AGENTS.md (Scope.PROJECT);
    # work/website, which has CLAUDE.md, gets none; .claude/AGENTS.md is read like AGENTS.md


def test_claude_code_reads_agents_md_beside_claude_md_with_the_setting(tmp_path, no_version):
    # ~/.claude/settings.json pluginConfigs["cc-plugin-agents-md@builtin"] = {"options":
    #   {"instructionFiles": "claude-md-and-agents-md"}} → work/website's AGENTS.md is listed too;
    # the old id "agents-md@builtin" works the same; "managed-only" lists no AGENTS.md


def test_an_old_claude_code_does_not_read_agents_md(tmp_path):
    # ClaudeCodeAdapter(home, read_version=lambda: "2.1.276") → no AGENTS.md item


def test_cursor_reads_agents_from_its_folders_and_claude_codes(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    found = {(i.scope, i.name, i.source.owner_client) for i in CursorAdapter(home).scan().items
             if i.kind is ItemKind.INSTRUCTIONS and dict(i.summary)["category"] == "agent"}
    assert found == {(Scope.USER, "planner", "cursor"), (Scope.USER, "reviewer", "claude_code"),
                     (Scope.USER, "notes", "claude_code"), (Scope.PROJECT, "site-tester", "cursor")}
```

  `test_explain.py`: `reads()` for Claude Code's `AGENTS.md` says
  `"Read when a session starts, because this project has no CLAUDE.md."`, or with the setting
  `"Read when a session starts, after CLAUDE.md (your Project instructions setting)."`.
- [ ] **Step 3: Run them to see them fail**: `uv run pytest tests/unit/test_read_claude_code.py tests/unit/test_read_cursor.py tests/unit/test_explain.py -v`.
- [ ] **Step 4: Implement.** Claude Code: agents through `agent_items(..., recursive=True, needs_name=True)`
  in both folders; project `AGENTS.md` and `.claude/AGENTS.md` by the rule above (skip a home-folder
  project's `.claude` files, as today). Cursor: `agent_items(..., recursive=False, needs_name=False)`
  for each of its six folders; `.claude/...` and `.codex/...` folders are `SourceKind.OTHER_CLIENT_FOLDER`
  owned by `claude_code` and `codex`. Each location gets its `# checked <date> (<url>)` comment.
  Update the expected sets of the read and library tests that count every item.
- [ ] **Step 5: Run** the three files and `uv run pytest tests/unit/test_library.py tests/unit/test_mcp_server.py tests/unit/test_demo_home.py tests/security -v` → PASS. (Part 1's sample agent `~/.claude/agents/reviewer.md` has `name: reviewer` and a description, so its contract test still finds it. Cursor now also lists it through `~/.claude/agents`: if that moves the medium count out of Part 1's 50–75 range, widen the range in `test_demo_home.py` in this commit.)
- [ ] **Step 6: Run all checks**, then commit

```bash
git add src/kitden/clients/base.py src/kitden/clients/claude_code.py src/kitden/clients/cursor.py src/kitden/views/skills.py src/kitden/views/explain.py tests/fixtures/claude_code/2.1.283/home/.claude/agents tests/fixtures/cursor/3.21.16/home/.cursor/agents tests/fixtures/cursor/3.21.16/home/work/site/.cursor/agents tests/unit/test_read_claude_code.py tests/unit/test_read_cursor.py tests/unit/test_explain.py tests/unit/test_library.py
git commit -m "Instructions: Cursor's agents, Claude Code's AGENTS.md, agents by name"
```

(Add `tests/unit/test_demo_home.py` only when Step 5 widened its range.)

---

### Task 3: The page notices changes in known projects

**Files:**
- Modify: `src/kitden/watch.py` (new `PROJECT_SUBFOLDERS`, `PROJECT_CAP`, `project_folders`,
  `Watcher.watch_projects`), `src/kitden/web/app.py` (`State.on_inventory`; `create_app` wires it
  to the watcher)
- Test: `tests/unit/test_watch.py`, `tests/unit/test_events.py`

**Interfaces:**
- Produces:
  - `PROJECT_SUBFOLDERS = (".claude", ".cursor", ".codex", ".agents")`, `PROJECT_CAP = 50`.
  - `project_folders(projects: Iterable[str], home: Path | None, cap: int = PROJECT_CAP) -> tuple[list[Path], list[Path]]`:
    the project roots to watch without sub-folders, and their `PROJECT_SUBFOLDERS` that exist, to
    watch with sub-folders. Skips a folder that is gone and the home folder (already watched); keeps
    the first `cap` projects in the order given, without repeats.
  - `Watcher.watch_projects(flat: list[Path], deep: list[Path]) -> None`: replaces the project
    folders it watches; a list equal to the last one changes nothing.
  - `State.on_inventory: Callable[[Inventory], None]` (default does nothing), called after every
    build (`_quick_first_scan`, `rescan`).

- [ ] **Step 1: Write the failing tests**

```python
def test_project_folders_skip_home_and_missing_folders_and_stop_at_the_cap(tmp_path):
    made = [tmp_path / f"p{i}" for i in range(60)]
    for p in made:
        (p / ".claude").mkdir(parents=True)
    flat, deep = project_folders([str(tmp_path), str(tmp_path / "gone"), *map(str, made)], tmp_path)
    assert flat == made[:50]
    assert deep == [p / ".claude" for p in made[:50]]


def test_the_watcher_follows_a_new_project_list(tmp_path):
    # watch_projects([a], []) then watch_projects([b], []); writing b/.mcp.json calls on_change once;
    # writing a/.mcp.json afterwards does not


def test_a_changed_file_in_a_known_project_triggers_a_rescan(tmp_path):
    # as test_a_changed_file_triggers_a_rescan, with watch_folders=[] and a build that returns an
    # Inventory whose projects hold tmp_path / "site"; writing site/.mcp.json → len(builds) >= 2
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_watch.py tests/unit/test_events.py -v`.
- [ ] **Step 3: Implement.** `watch_projects` stops the project loops (their own stop event, not
  the watcher's) and starts new ones; `stop()` ends them too. Over the cap, one line on stderr
  once: "Kitden watches the first 50 projects; Rescan reads the others."
- [ ] **Step 4: Run** both files → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/watch.py src/kitden/web/app.py tests/unit/test_watch.py tests/unit/test_events.py
git commit -m "Live page: watch the known projects' setup files too"
```

---

### Task 4: Safer writes to `~/.claude.json`, and Undo without a server error

**Files:**
- Modify: `src/kitden/changes/engine.py` (`_verify`, the restore in `_apply`, `undo`)
- Test: `tests/unit/test_engine.py`, `tests/unit/test_copy_folder.py`

**Interfaces:**
- Consumes: `FileEdit.check == "entry"` (set by `ClaudeCodeAdapter._add_entry` and the other
  `~/.claude.json` steps) and `_undo_entries(steps, data)` (already puts entries back one by one).
- Produces: no new name. Behaviour:
  - Apply verifies an entry-check edit by its entry only; the exact-bytes check stays for
    `check == "file"`.
  - After a failed Apply, a file whose steps are all entry-check and not by command gets
    `_undo_entries(steps, now)` written, not its old bytes; when an entry is no longer Kitden's,
    the file is left and the error adds
    `f"{edit.path}: {step.name} changed while Kitden applied; check it by hand."`.
  - Undo ends in `UNDO_BLOCKED` with one plain sentence, never an exception, when a copied folder
    cannot be removed (`f"{target} could not be removed. Check it by hand."`), a removed folder
    cannot be copied back (`f"{path} could not be put back; its backup is in {backup}."`), or a
    file does not read back (`f"{path} did not read back as expected after Undo. Check it by hand."`).

- [ ] **Step 1: Write the failing tests** (a new helper `direct_step(path, name, after)` makes
  `claude_step`'s entry-check edit with the default mechanism and no command, as
  `ClaudeCodeAdapter._add_entry` does for an entry with a secret; Claude Code's own write is
  simulated in the engine's `on_write` hook, once, right after Kitden's write)

```python
def test_a_direct_write_keeps_an_update_claude_code_makes_meanwhile(tmp_path, claude_json):
    # on_write: the first time it sees .claude.json, set numStartups to 2 in the file
    # apply → change.state is ChangeState.VERIFIED
    # the file has mcpServers.files == the new entry and numStartups == 2


def test_a_failed_change_takes_back_only_its_entry_in_claude_json(tmp_path, claude_json):
    # steps: the direct entry, then a client_cli step on another file whose command fails
    # on_write sets numStartups to 2 after Kitden's write
    # apply → RESTORED; mcpServers.files is ABSENT; numStartups == 2; mcpServers.old unchanged


def test_a_failed_change_leaves_an_entry_claude_code_changed_meanwhile(tmp_path, claude_json):
    # as above, but on_write also changes mcpServers.files; after RESTORED the entry stays
    # and change.error contains "files changed while Kitden applied; check it by hand."
```

```python
def test_an_undo_that_cannot_remove_the_copy_says_so(tmp_path, places, monkeypatch):
    # apply a copy_step; monkeypatch kitden.changes.engine.remove_folder to raise OSError
    # engine.undo(id) returns; state is UNDO_BLOCKED; error == f"{target} could not be removed. Check it by hand."
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_engine.py tests/unit/test_copy_folder.py -v`.
- [ ] **Step 3: Implement.** Update the module docstring's "entry" paragraph: Apply's check, a
  failed Apply and Undo all touch only the entry.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_engine.py tests/unit/test_copy_folder.py tests/unit/test_claude_code_secret_entry.py tests/unit/test_local_gateway_move.py -v` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/changes/engine.py tests/unit/test_engine.py tests/unit/test_copy_folder.py
git commit -m "Engine: a direct write to ~/.claude.json keeps Claude Code's own update" -m "Undo ends plainly when a folder cannot be put back."
```

---

### Task 5: One rule for "loads twice", and what Cursor follows from Claude Code

**Files:**
- Modify: `src/kitden/views/skills.py` (new `skills_loaded`), `src/kitden/changes/align.py`
  (`align_steps` twice check), `src/kitden/views/after.py` (`_skill_words`, `_align_words`,
  `after_words`), `src/kitden/web/app.py` (`preview`: the `plugins` tuple and comment, `project`
  for `after_words`)
- Test: `tests/unit/test_after.py`, `tests/unit/test_align.py`, `tests/unit/test_plugins.py`

**Interfaces:**
- Consumes: the words of `views/words.py STATE_WORDS` (Part 2) where it has them.
- Produces:
  - `skills_loaded(inventory, skills: list[dict], project: str | None) -> dict[str, set[str]]`:
    client → names of the skills it loads now in `project`: its user and plugin skills that are
    not off, its skills of that project, and the clients a skill-list row's `installed` names.
  - `after_words(change, inventory, cursor_imports=False, skills=None, home=None, project: str | None = None)`.
  - Cursor entries in the After chips when Cursor imports Claude Code's plugins and the step is a
    Claude Code user plugin:
    - `plugin.disable`, Cursor has no other copy: `{"client": "cursor", "state": "off", "word": "Off", "note": "Cursor loads Claude Code plugins, so it turns this one off too."}`
    - `plugin.disable`, Cursor keeps another copy: `{"client": "cursor", "state": "on", "word": "Loads once", "note": "Cursor loads Claude Code plugins, so it turns this copy off and keeps {its own | the other Claude Code copy}."}`
    - `plugin.enable`, no other copy: `{"client": "cursor", "state": "on", "word": "Loads", "note": "Cursor loads Claude Code plugins, so it turns this one on too."}`
    - `plugin.enable` or `plugin.install` while Cursor loads another copy (not off): `{"client": "cursor", "state": "on", "word": "Loads twice", "note": "Cursor loads Claude Code plugins, so it then loads this copy and {its own | the other Claude Code copy}."}`

- [ ] **Step 1: Write the failing tests**

```python
def test_turning_off_a_claude_code_user_plugin_names_cursor_too():
    inv = inventory(plugin("claude_code", "notes@official", "/h/a.json"), imported("notes@official"))
    change = Change(action="plugin.disable", steps=[step("claude_code", "notes@official")])
    assert after_words(change, inv, cursor_imports=True)[1] == {
        "client": "cursor", "state": "off", "word": "Off",
        "note": "Cursor loads Claude Code plugins, so it turns this one off too.",
    }


def test_a_project_plugin_switch_does_not_name_cursor():
    # the same with Step(scope=Scope.PROJECT) → only the Claude Code entry


def test_installing_a_claude_code_plugin_cursor_has_says_cursor_loads_it_twice():
    # Cursor's own notes@cursor-mkt is on → the Cursor entry is "Loads twice" with "and its own."
```

  (`imported(name)` is a new helper: a Cursor plugin item with `SourceKind.OTHER_CLIENT_FOLDER`,
  owner `claude_code`.)

```python
def test_add_missing_and_its_review_agree_on_a_project_skill_loaded_twice(home):
    # work/api: a project skill Cursor loads (in the project folder Cursor's adapter reads) that
    # Claude Code lacks; the Claude Code add's copy reaches Cursor:
    # its listing["will_add"] entry (Part 4) has note "Cursor would load it twice." and chosen False;
    # checked by hand, the review's Cursor chip word is "Loads twice"


def test_add_missing_with_cursor_importing_does_not_name_cursor_for_a_project_plugin(home):
    # a Claude Code plugin candidate has place "project"; no After entry for Cursor comes from it
```

  `test_plugins.py`: a `plugin.disable` preview of a Claude Code user plugin, with Cursor's import
  on, has a Cursor entry in `after`.
- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_after.py tests/unit/test_align.py tests/unit/test_plugins.py -v`.
- [ ] **Step 3: Implement.** `align_steps` and `_skill_words` both read `skills_loaded`; app.py
  passes the project path the steps write into, and `cursor_imports` for `PLUGIN_ENABLE` and
  `PLUGIN_DISABLE` too (the comment says Cursor follows Claude Code's switches).
- [ ] **Step 4: Run** the three files and `uv run pytest tests/unit/test_project_add.py tests/unit/test_api_skill_install.py -v` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/views/skills.py src/kitden/changes/align.py src/kitden/views/after.py src/kitden/web/app.py tests/unit/test_after.py tests/unit/test_align.py tests/unit/test_plugins.py
git commit -m "Reviews: one rule for loading twice; Cursor follows Claude Code's plugin switches"
```

---

### Task 6: Keychain sentences and tokens with a line break

**Files:**
- Modify: `src/kitden/local_gateway/keychain.py` (`NAME_REFUSED`, `needs_hex`, `check_account`,
  `store`, `read`, `is_reference`, `_value`), `src/kitden/model.py` (`KeychainItem.hex`, `ref`),
  `src/kitden/changes/actions.py` (`secrets_out`), `src/kitden/changes/engine.py`
  (`_store_secrets`, the restore's Keychain lines)
- Test: `tests/unit/test_keychain.py`, `tests/unit/test_local_gateway_move.py`

**Interfaces:**
- Produces:
  - `NAME_REFUSED = '{account} cannot name a Keychain item: it has " or \\ in it.'`;
    `check_account(account: str) -> None` raises `KeychainError(NAME_REFUSED.format(account=account))`;
    `secrets_out` calls it and turns it into a `ValueError` at preview; `store` keeps it as its guard.
  - `needs_hex(value: str) -> bool`: `not (value.isascii() and value.isprintable())`. Such a value
    is stored as its hex text, and its reference is `{"keychain": "<server>/<key>", "hex": True}`;
    `read` decodes it. `is_reference` accepts exactly the keys `keychain` and, optionally, `hex: True`.
    (`security -w` is not documented for a value with a line break; this form never asks it.)
  - `KeychainItem.hex: bool = False`, set in `secrets_out`; `ref` adds `"hex": True` when set.
  - `_value`: with no "/" in the account, "Kitden could not read a secret from the Keychain."
  - `_store_secrets(change, stored: list[KeychainItem], written: list[KeychainItem])`: `stored`
    before each write, `written` after it. The restore says, for an item that was there before:
    in `written`, `"{server}/{key} in your Keychain keeps the new value."`; not in `written`,
    `"{server}/{key} in your Keychain may hold the new value."`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_value_with_a_line_break_is_kept_as_hex_and_reads_back(fake_run):
    ref = store("files", "TOKEN", "tok\n", run=fake_run)
    assert ref == {"keychain": "files/TOKEN", "hex": True}
    assert fake_run.items["kitden files/TOKEN"] == "746f6b0a"
    assert read(ref, run=fake_run) == "tok\n"


def test_a_name_with_a_quote_is_refused_with_its_own_sentence(fake_run):
    with pytest.raises(KeychainError, match=r'^files/MY"KEY cannot name a Keychain item'):
        store("files", 'MY"KEY', "x", run=fake_run)


def test_a_reference_without_a_slash_gives_a_whole_sentence(fake_run):
    with pytest.raises(KeychainError, match="^Kitden could not read a secret from the Keychain.$"):
        resolve_entry({"env": {"A": {"keychain": "nothing"}}}, run=fake_run)
```

```python
def test_a_token_with_a_line_break_moves_and_comes_back_unchanged(home, fake_keychain):
    entry = {**FILES, "env": {"FILES_TOKEN": "SENTINEL_SECRET_FILES\n"}}
    add_claude(home, "files", {"type": "stdio", **entry})
    apply(home, move(home, ("claude_code", "files")))
    held = load_settings(home)["servers"]["files"]
    assert held["env"]["FILES_TOKEN"] == {"keychain": "files/FILES_TOKEN", "hex": True}
    assert resolve_entry(held)["env"]["FILES_TOKEN"] == "SENTINEL_SECRET_FILES\n"


def test_a_name_the_keychain_cannot_take_is_refused_at_preview(home):
    # env key 'MY"KEY' → refused(home, ("claude_code", "files"), 'files/MY"KEY cannot name a Keychain item: it has " or \\ in it.')


def test_a_restore_says_an_item_whose_own_write_failed_may_hold_the_new_value(home, fake_keychain, monkeypatch):
    # as test_a_restore_says_an_item_that_was_there_keeps_the_new_value, with keychain.store
    # monkeypatched to raise KeychainError → RESTORED, error ends with
    # " files/FILES_TOKEN in your Keychain may hold the new value."
```

  (`fake_run` is a small in-memory runner in `test_keychain.py` if the file has none.)
- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_keychain.py tests/unit/test_local_gateway_move.py -v`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** both files, `tests/unit/test_local_gateway_proxy.py` and `tests/security` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/local_gateway/keychain.py src/kitden/model.py src/kitden/changes/actions.py src/kitden/changes/engine.py tests/unit/test_keychain.py tests/unit/test_local_gateway_move.py
git commit -m "Keychain: tokens with a line break move; true sentences when a write fails"
```

---

### Task 7: Gateway: last good rules, the batch line, Put back, call times

**Files:**
- Modify: `src/kitden/local_gateway/settings.py` (new `read_settings`, `allows`; `is_allowed`
  goes), `src/kitden/local_gateway/proxy.py` (`_Gateway.last_good`, `call_tool`),
  `src/kitden/local_gateway/views.py` (`rule_of`), `src/kitden/web/app.py` (`_with_rule` for both
  rule actions), `src/kitden/views/after.py` (`_put_back_words`)
- Modify: `src/kitden/web/static/js/parts.js` (`changeTitle`), `src/kitden/web/static/js/details.js`
  (new `putBackClients`, used where `heldActions` is called), `src/kitden/web/static/js/gateway.js`
  (`showKitdenServer`), `src/kitden/web/static/js/tools.js` (`callsText`)
- Test: `tests/unit/test_local_gateway_settings.py`, `tests/unit/test_local_gateway_proxy.py`,
  `tests/unit/test_local_gateway_views.py`, `tests/unit/test_after.py`,
  `tests/frontend/parts.test.mjs`, `tests/frontend/details.test.mjs` (`putBackClients`),
  `tests/frontend/tools.test.mjs` (Part 5's; the new `callsText` case),
  `tests/frontend/panel.test.mjs` (the `TZ` fix in 'calls text says how many and when')

**Interfaces:**
- Consumes: Part 5's `callsText(calls, now)` ("12 calls · last today 14:02").
- Produces:
  - `read_settings(home: Path) -> dict | None`: the settings when the file reads as a JSON object,
    None when it is missing or unreadable. `allows(settings: dict, chain: Sequence[str], server: str, tool: str) -> bool`:
    the server is held and both it and the tool are on along the chain.
  - `_Gateway.last_good: dict` (the settings at start); each call reads `read_settings`, keeps a
    good read as `last_good`, and decides with `allows(self.last_good, …)`.
  - `rule_of(change)` also answers `gateway.rules`: `{"project", "server", "tool": None, "tools": [names], "state"}`.
  - `changeTitle` of `gateway.rules` with `rule`: `rulesText(rule, rule.project).done`
    ("Turned off 3 tools of github in website"); without it: `` `Changed the rules for ${plural(n, "tool", "tools")} · Kitden gateway` ``.
  - `putBackClients(clients: string[], definitions: {client, scope, via_gateway}[]) -> string[]`:
    the clients without a user-scope direct definition of that name.
  - `callsText` with a `last` that is not a date: the count alone ("3 calls").
  - Put back's note, when the server is off for all projects but on in projects:
    `"{Client} then loads {server} twice in {folders}: directly and through the Kitden gateway. Remove it from the gateway to keep one."`
    (`folders`: the folder names, joined by ", ").

- [ ] **Step 1: Write the failing tests**

```python
async def test_a_tool_turned_off_stays_refused_when_the_rules_file_then_breaks(home):
    write_settings(home, {"echo": echo("echo")})
    save_tools(home, "echo", [tool("echo"), tool("where")])
    async with gateway(home) as client:
        await client.list_tools()
        write_settings(home, {"echo": echo("echo")}, {"global": {"echo": {"tools": {"echo": "off"}}}})
        first = await client.call_tool("echo", {"text": "hi"})
        (data_dir(home) / SETTINGS_FILE).write_text("{ not json")
        again = await client.call_tool("echo", {"text": "hi"})
        works = await client.call_tool("where", {})
    assert first.is_error and again.is_error and text(again) == "echo is turned off in Kitden."
    assert not works.is_error
```

  `test_local_gateway_settings.py`: the five `is_allowed` tests become `read_settings` + `allows`
  tests with the same cases (a missing or broken file reads None; a server not in the file is
  not allowed; a tool on under a server off is refused; strict mode).

```python
def test_rule_of_names_a_batch_with_its_tools_and_state(home):
    # a previewed gateway.rules change for github, tools a and b, off, project website →
    # {"project": "website", "server": "github", "tool": None, "tools": ["a", "b"], "state": "off"}


def test_put_back_names_the_projects_where_the_gateway_still_offers_it(tmp_path, monkeypatch):
    # github off for all projects, on in work/website; Claude Code offers the gateway →
    # note "Claude Code then loads github twice in website: directly and through the Kitden gateway. …"
```

```js
// parts.test.mjs
test('the Changes line of a batch says on or off and counts the tools', () => {
  const steps = ['a', 'b', 'c'].map((name) => ({ client: 'gateway', name }));
  assert.equal(changeTitle({ action: 'gateway.rules', steps, rule: { project: 'website', server: 'github', tools: ['a', 'b', 'c'], state: 'off' } }), 'Turned off 3 tools of github in website');
  assert.equal(changeTitle({ action: 'gateway.rules', steps }), 'Changed the rules for 3 tools · Kitden gateway');
});
// details.test.mjs (import putBackClients from details.js)
test('Put back is offered only to clients without an entry of that name', () => {
  const defs = [{ client: 'codex', scope: 'user', via_gateway: null }, { client: 'cursor', scope: 'project', via_gateway: null }, { client: 'claude_code', scope: 'user', via_gateway: 'kitden' }];
  assert.deepEqual(putBackClients(['claude_code', 'codex', 'cursor'], defs), ['claude_code', 'cursor']);
});
// tools.test.mjs (callsText from tools.js)
test('a call time that cannot be read shows the count alone', () => {
  assert.equal(callsText({ count: 3, last: 'nope' }, new Date()), '3 calls');
});
```

  The test that sets `process.env.TZ = 'UTC'` keeps the old value and puts it back in a `finally`
  (deleting it when it was unset). `parts.test.mjs` pins today's batch line
  ('Changed the rules for create_issue, delete_issue · Kitden gateway'): it takes the new words.
  The `heldActions` tests and `test_page_words.py`'s "Put back in" pin stay as they are.
- [ ] **Step 2: Run them to see them fail** (`uv run pytest tests/unit/test_local_gateway_settings.py tests/unit/test_local_gateway_proxy.py tests/unit/test_local_gateway_views.py tests/unit/test_after.py -v`, `node --test tests/frontend/*.test.mjs`).
- [ ] **Step 3: Implement.** The Gateway page's held-server Details reads `/api/explain` for the
  server's name before it draws its buttons, so it has the definitions `putBackClients` needs.
- [ ] **Step 4: Run** the same commands → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/local_gateway/settings.py src/kitden/local_gateway/proxy.py src/kitden/local_gateway/views.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/parts.js src/kitden/web/static/js/gateway.js src/kitden/web/static/js/details.js src/kitden/web/static/js/tools.js tests/unit/test_local_gateway_settings.py tests/unit/test_local_gateway_proxy.py tests/unit/test_local_gateway_views.py tests/unit/test_after.py tests/frontend/parts.test.mjs tests/frontend/details.test.mjs tests/frontend/tools.test.mjs tests/frontend/panel.test.mjs
git commit -m "Gateway: the last good rules decide; Put back only where it works" -m "The Changes line of a batch says on or off."
```

---

### Task 8: Page: fold back, one start read, set-up for every client, a quick stop

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (`visibleRows`, the group list),
  `src/kitden/web/static/js/overview.js` (`gatewayCardWords`, `gatewayCard`),
  `src/kitden/web/static/js/app.js` (`start`), `src/kitden/clients/version_cache.py`
  (`run_version_command`, new `stop_version_commands`), `src/kitden/web/app.py` (`lifespan`),
  `docs/design.md` (Gateway page fold; the Overview gateway card)
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/overview.test.mjs`,
  `tests/unit/test_page_words.py`, `tests/unit/test_overview.py`, `tests/unit/test_version_cache.py`

**Interfaces:**
- Consumes: Part 2 Task 6's handling of a project no longer on the list: `loadShared` no longer
  resets the project, and `reload()` (which calls `loadShared` first) reads no project data while
  `projectGone()`. So `start()` no longer needs its own early `loadShared()` call: it calls
  `refresh()` only, and the start reads `/api/clients`, `/api/projects` and `/api/changes` once.
  `loadShared` stays exported from `store.js` (`reload()` and Part 8's tour call it).
- Produces:
  - `visibleRows(rows, expanded, limit = FOLD_AT) -> { shown, cut, fewer }`; `fewer` is true when
    `expanded` and `rows.length > limit`. A quiet "Show fewer" (`btn small ghost`) after an open
    group folds it; focus goes to its "Show all N" button (the existing `show:${key}` focus key).
  - `gatewayCardWords(gateway) -> { title, line, problem, actions }`: no gateway →
    `{ title: "Gateway", line: "No gateway yet.", problem: null, actions: ["Set up"] }`; the Kitden
    gateway → `line` the servers and clients joined by " · ", or null; `problem` the problem or
    null; `actions` one `` `Set up in ${CLIENT_NAMES[c]}…` `` per client in `lacking`. The card
    draws the problem as a `p.callout` under the line. "Nothing in it yet." goes.
  - `version_cache.stop_version_commands() -> None`: kills every version command still running;
    `run_version_command` then returns None. `lifespan` calls it before it waits for its tasks.

- [ ] **Step 1: Write the failing tests**

```js
test('an open group can fold back', () => {
  const rows = Array.from({ length: 7 }, (_, i) => ({ name: `s${i}` }));
  assert.deepEqual(visibleRows(rows, true), { shown: rows, cut: 0, fewer: true });
  assert.deepEqual(visibleRows(rows, false), { shown: rows.slice(0, 6), cut: 1, fewer: false });
  assert.deepEqual(visibleRows(rows.slice(0, 6), true), { shown: rows.slice(0, 6), cut: 0, fewer: false });
});
test('the gateway card offers set-up to every client that lacks it', () => {
  const words = gatewayCardWords({ kind: 'kitden', name: 'Kitden gateway', servers: 1, clients: ['claude_code'], lacking: ['codex', 'cursor'], problem: null });
  assert.deepEqual(words.actions, ['Set up in Codex…', 'Set up in Cursor…']);
});
test('a problem shows beside the servers and clients, not instead of them', () => {
  const words = gatewayCardWords({ kind: 'kitden', name: 'Kitden gateway', servers: 0, clients: ['cursor'], lacking: [], problem: 'Kitden could not read the gateway settings.' });
  assert.equal(words.line, 'Cursor');
  assert.equal(words.problem, 'Kitden could not read the gateway settings.');
  assert.deepEqual(words.actions, []); // a client with an old entry is not lacking
});
```

  The three existing `visibleRows` and `gatewayCardWords` tests take the new shapes.

```python
def test_the_overview_route_passes_held_servers_and_the_problem(tmp_path):
    # a home with a held server and a broken gateway.json → /api/overview's gateway has
    # "problem": "Kitden could not read the gateway settings."; with a good file, "servers": 1


def test_the_start_reads_shared_data_once():
    assert "loadShared" not in script("app.js")


def test_an_open_gateway_group_folds_back():
    assert '"Show fewer"' in script("gateway.js")
    assert "Nothing in it yet." not in script("overview.js")


def test_stopping_the_page_does_not_wait_for_a_version_command(tmp_path, monkeypatch):
    # a fake client command that writes a marker, then `exec sleep 30`; version_command patched to it;
    # create_app(build, token, port, version_refresh=lambda: {"cursor": run_version_command("cursor")},
    #            first_scan_later=True, quick_first=True)
    # with TestClient(app): wait for the marker; leaving the block takes under 3 s


def test_stop_version_commands_ends_a_running_one(tmp_path, monkeypatch):
    # run_version_command in a thread; after the marker, stop_version_commands(); the thread
    # ends within 2 s and the answer is None
```

- [ ] **Step 2: Run them to see them fail** (`node --test tests/frontend/*.test.mjs`, `uv run pytest tests/unit/test_page_words.py tests/unit/test_overview.py tests/unit/test_version_cache.py -v`).
- [ ] **Step 3: Implement.** `start()` calls `refresh()` only. `run_version_command` runs the
  command with `subprocess.Popen` (looked up at call time, so the test guard still applies) and
  keeps it in a set under a lock until it ends. `docs/design.md`: the Gateway page "folds a group
  after six rows; Show fewer folds it back"; a Components line for the Overview gateway card (one
  "Set up in <client>…" per client without the entry; a settings problem as a callout under the line).
- [ ] **Step 4: Run** the same commands → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/web/static/js/gateway.js src/kitden/web/static/js/overview.js src/kitden/web/static/js/app.js src/kitden/clients/version_cache.py src/kitden/web/app.py docs/design.md tests/frontend/gateway.test.mjs tests/frontend/overview.test.mjs tests/unit/test_page_words.py tests/unit/test_overview.py tests/unit/test_version_cache.py
git commit -m "Page: fold a group back, set up every client, read once at start" -m "Ctrl+C no longer waits for a client's version command."
```

---

### Task 9: Small items: copied entries, tests and the fixtures README

**Files:**
- Modify: `src/kitden/changes/server_entry.py` (`_canonical`, `_codex`, `_CURSOR_VARIABLE` and
  `_MARKED` refusals), `src/kitden/web/static/js/library.js` (`addChoices()` takes no arguments;
  its caller), `scripts/measure-start.py` (HOME put back), `tests/fixtures/README.md`
- Test: `tests/unit/test_server_entry.py`, `tests/unit/test_findings.py`,
  `tests/unit/test_remove_plugin.py`, `tests/unit/test_inventory.py`,
  `tests/frontend/library.test.mjs`, `tests/frontend/details.test.mjs` (the new `offerLabel` case;
  `offerLabel` is in `details.js` since Part 3)

**Interfaces:**
- Produces (copy fixed here):
  - An entry with both `command` and `url`: `UNREADABLE` ("The entry could not be read.").
  - A header named `Authorization` in any case is matched as `Authorization` for Codex.
  - `bearer_token_env_var` together with an `Authorization` header: "The entry sets Authorization twice; keep one."
  - A `${…}` refusal names the text only when it is a plain name (`[A-Za-z_][A-Za-z0-9_]*`) closed
    by `}`; otherwise "The entry uses a `${…}` that {Client} cannot read." (Cursor variable) or
    "The entry holds a `${…}` as plain text; {Client} would fill it in." (Codex literal).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_refusal_never_shows_text_that_is_not_a_variable_name():
    for entry, client, source in (
        ({"url": "https://x/a?k=${tok-SENTINEL_SECRET_X"}, "claude_code", "cursor"),
        ({"command": "run", "args": ["--k=${SENTINEL_SECRET_Y"]}, "claude_code", "codex"),
    ):
        with pytest.raises(ValueError) as refused:
            translate_entry(entry, client, source=source)
        assert "SENTINEL_SECRET" not in str(refused.value)


def test_an_entry_with_a_command_and_an_address_is_refused():
    with pytest.raises(ValueError, match="^The entry could not be read.$"):
        translate_entry({"command": "x", "url": "https://y"}, "claude_code")


def test_a_lowercase_authorization_header_becomes_codexs_bearer_variable():
    out = translate_entry({"url": "https://x", "headers": {"authorization": "Bearer ${TOK}"}}, "codex")
    assert out["bearer_token_env_var"] == "TOK"


def test_a_token_set_twice_is_refused():
    entry = {"url": "https://x", "bearer_token_env_var": "A", "http_headers": {"Authorization": "Bearer lit"}}
    with pytest.raises(ValueError, match="^The entry sets Authorization twice; keep one.$"):
        translate_entry(entry, "cursor", source="codex")


def test_a_plugin_provided_kitden_entry_is_not_flagged():
    # the kitden server from the kitden plugin (Scope.PLUGIN) in two clients → no finding names it


def test_a_project_plugin_remove_applies_and_undoes(client):
    # as test_a_project_plugin_is_removed_from_its_project, then Apply and Undo with the fake
    # `claude`: uninstall runs with -s project in the project folder; Undo installs it there again
```

```js
// details.test.mjs (import offerLabel from details.js)
test('two actions of one definition are not twins', () => {
  // a toggle and a remove offer for the same def → 'Remove from Codex…' with no folder
});
```

  The existing refusals with a plain variable name (`test_cursors_own_variables_stay_in_cursor`,
  `test_a_codex_literal_stays_plain_text`) keep their exact words.
  `test_inventory.py`: `test_the_first_scan_runs_no_version_command` bounds the time at `< 2.5`
  (the command sleeps 3 s; `not ran.exists()` is the real check). `library.test.mjs`: the two
  local `const row` become `const item`.
- [ ] **Step 2: Run them to see them fail** (the test-only items pass at once: say so).
- [ ] **Step 3: Implement**; `tests/fixtures/README.md` names the folders that exist
  (`claude_code/2.1.283`, `codex/0.159.2`, `cursor/3.21.16`, `apps/`, `fake_mcp/`,
  `fake_security.py`), drops `sandbox-home/`, and says the demo samples are built by
  `kitden.demo.build_demo_home` (Part 1), not kept here. `measure-start.py` pops `HOME` and
  `PATH` that were unset instead of setting them to "".
- [ ] **Step 4: Run** the test files above and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/changes/server_entry.py src/kitden/web/static/js/library.js scripts/measure-start.py tests/fixtures/README.md tests/unit/test_server_entry.py tests/unit/test_findings.py tests/unit/test_remove_plugin.py tests/unit/test_inventory.py tests/frontend/library.test.mjs tests/frontend/details.test.mjs
git commit -m "Copied entries: refusals never show a token" -m "Small test fixes and a fixtures README that matches."
```

---

### Task 10: Docs and roadmap for Part 7

**Files:**
- Modify: `docs/development.md`, `tests/unit/test_docs_words.py`; `ROADMAP.md` only under the rule
  below. `README.md`: no change unless a sentence became false (Part 8 rewrites it).

- [ ] **Step 1: `docs/development.md`.** Gateways: "if the file cannot be read, the last rules it
  read apply"; a Keychain reference may carry `"hex": true` (a value with a line break or a
  non-ASCII letter is kept as hex text); Kitden's data folder also holds `versions.json` (see
  Speed); wrap the paragraph at 100 characters. Release hand check: step 21's `-w` fact becomes
  "a token with a line break or a non-ASCII letter moves in; the server gets it unchanged"; new
  step 23: "Cursor's agent list shows an agent from `~/.claude/agents`, and the Library shows
  Cursor has it; in a project with only `AGENTS.md`, Claude Code's `/context` lists it and the
  Library shows Claude Code has it"; new step 24: "Change a known project's `.mcp.json` while the
  page runs; the page shows it within a few seconds." Mark 23–24 "Not run yet".
- [ ] **Step 2: Pin the fallback sentence**

```python
def test_development_says_the_last_good_rules_apply():
    text = " ".join((ROOT / "docs/development.md").read_text().split())
    assert "the last rules it read apply" in text and "the rules it started with" not in text
```

- [ ] **Step 3: ROADMAP.** If `git status` shows `ROADMAP.md` modified and not by this part, do not
  touch it; put these lines in the report instead. Otherwise add them under "### Not released yet"
  (moving the part's line out of "## Planned" if it has one):
  - **Live projects:** the page notices changes in your known projects' setup files.
  - **Safer writes:** when Claude Code updates `~/.claude.json` during a change, its update is
    kept; a failed change takes back only Kitden's entry.
  - **Agents and AGENTS.md:** the Instructions tab shows the agents Cursor reads from
    `.claude/agents`, and `AGENTS.md` where Claude Code reads it.
  - **Fixes:** a tool turned off stays refused when the rules file breaks; the Changes page says on
    or off for a batch; Put back only where it works; tokens with a line break move into the
    Keychain; a gateway group folds back; Ctrl+C stops at once.
  - For the owner: the "## Planned" Part 5 line says OAuth servers move; they stay direct (5.3
    waits for the owner).
- [ ] **Step 4: Run all checks**, then commit

```bash
git add docs/development.md tests/unit/test_docs_words.py
git commit -m "Docs: Part 7 leftovers"
```

---

## Builder calls (decisions the spec does not settle)

- Builder call: the map is hidden by one constant, `MAP_SWITCH = false` in `store.js` (where `overviewMode()` and `reload()` read it); every way into the map (the switch, "Show on the map", a map selection in the address, a saved "map" choice) falls back to the list.
- Builder call: Cursor reads `*.md` agents directly in each of its six folders, not sub-folders (its docs do not say); the name is `name:` or the file name. The `.claude` and `.codex` folders follow "Include Third-Party Plugins" only if Cursor's docs say so.
- Builder call: Claude Code agents are named by `name:` only; a file without `name` or `description` is not listed; sub-folders are read.
- Builder call: Claude Code's `AGENTS.md` is listed at a project root only, when the rule allows it and Claude Code's version is not known to be below 2.1.277; `managed-only` lists no `AGENTS.md` (Kitden still lists the CLAUDE.md files it hides: not built here).
- Builder call: Codex's own agents (`.codex/agents/*.toml`) are not read; the spec does not ask.
- Builder call: the watcher watches each project root without sub-folders and its `.claude`, `.cursor`, `.codex`, `.agents` with them (the spec names fewer; Kitden reads all of these); 50 projects at most, in the inventory's order, with one log line over the cap.
- Builder call: the watcher learns the project list through `State.on_inventory`, after every build.
- Builder call: after a failed Apply, an entry someone changed meanwhile is left as it is and named in the error.
- Builder call: an Undo that fails halfway on a folder or a read-back ends in `UNDO_BLOCKED` with a sentence, like a failed inverse command today.
- Builder call: `after_words` gains `project`; one helper, `skills_loaded`, decides "loads twice" for Add missing and the review.
- Builder call: Cursor follows only Claude Code's user plugin switches (it reads `~/.claude/settings.json` only).
- Builder call: a Keychain value that is not printable ASCII is stored as hex text with `"hex": true` in its reference, so Kitden never relies on how `security -w` prints a line break.
- Builder call: the "may hold the new value" sentence (the parked ruling's words) replaces the spec's "may keep the new value".
- Builder call: `is_allowed` goes; `read_settings` and `allows` replace it, and its tests move with it.
- Builder call: the batch's Changes line without a readable record counts the tools instead of listing them.
- Builder call: Put back's note names the projects when only project rules offer the server; the Gateway page's held Details reads `/api/explain` to know which clients have the name.
- Builder call: a call time that cannot be read shows the count alone.
- Builder call: "Show fewer" sends focus back to the group's "Show all N".
- Builder call: the gateway card shows a settings problem as a callout under the line, not instead of it.
- Builder call: only version commands are stopped on Ctrl+C; Codex's plugin list is not in this part.
- Builder call: an entry with both a command and an address, or with its token set twice, is refused rather than guessed.
- Builder call: the first-scan timing bound becomes 2.5 s; the check that no command ran stays.
