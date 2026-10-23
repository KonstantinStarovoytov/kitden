# Part 7: Leftovers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix what the owner's second walkthrough found, then fix or close every minor finding
that the reviews of the earlier Parts 1–6 deferred, each with a test or a one-line reason. Also
build the two Gateway items the map re-plan moved here from the old Part 5.

**Architecture:** No new feature beyond those two items (Task 10). Task 1 holds the walkthrough
fixes the controller rules on. Tasks 2–9 each fix one area of the deferred list: what clients
read, the live page, writes to `~/.claude.json`, the "loads twice" rule, the Keychain, the
gateway, the page, and small items. Task 10 builds the writing-tools checklist and the rules for
folders Kitden no longer finds. Task 11 updates the docs. The triage table below says, for every
deferred item, whether it is fixed here, already fixed, settled by another part, or closed with a
reason.

**Tech Stack:** Python 3.13, Starlette, MCP SDK 2.3, watchfiles; plain ES modules, one CSS
file; pytest on sandbox homes and the Part 1 samples; node's test runner.

**Specs:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 7, built on
`docs/research/visual-management-ux-concept-2026-10-22.md`; and
`docs/superpowers/specs/2026-10-23-map-pages-design.md` ("What changes" and "Order") for what
moved here from the old Parts 4–6. Master plan:
`docs/superpowers/plans/2026-10-22-visual-management.md` (its Rules and "Names that cross part
boundaries" bind this plan). The raw deferred list is kept with the plan, outside the
repository.

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
  `checked <date of the check>` next to it. What the docs do not confirm is written as "not
  checked" and not built.
- Tests use `make_home(...)` / `write_cursor_fixture_state(home)` or `build_demo_home(root, size)`
  (Part 1). No real `claude`, `codex`, `cursor` or `security`, no real Keychain, no network, never
  the real home folder.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`,
  `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`. Stage files by
  name; never `git add -A`, `git add .` or `git commit -a`.
- `ROADMAP.md`: while `git status` shows it modified and not by this part, no task edits or
  stages it; Task 11 writes the lines into the part's report instead.
- Check first: each task starts by checking its items against `main` (after Parts 1–6). An item
  that is already fixed is closed with one line in the report. An item the triage marks
  "superseded by map Part N" that map Part N did not settle moves into Task 9 with a test. An
  item marked "re-check after map Part 4" is checked against `main` in Task 8 the same way.
- Line numbers are hints; find code by name. Part 3 splits `panel.js` into `panel.js` (shell and
  re-exports), `details.js`, `tools.js` and `review.js`. Map Part 4 adds `gateway-details.js`:
  the cards of a tool, a held server, an outside server, a client and the gateway (`toolCard`,
  `heldCard`, `outsideCard`, `clientCard`, `gatewayCard`, `callsText`), reached through `gw()` in
  `test_page_words.py`; map Part 5 empties `tools.js`. Each task below names the module that
  defines the function (`heldActions` and `offerLabel` in `details.js`, `callsText` and the
  held server's Details in `gateway-details.js`). New node tests go in that module's test file
  (`details.test.mjs`, `gateway-details.test.mjs`, `review.test.mjs`); existing tests in
  `panel.test.mjs` are edited where they are.

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
6. A tool Kitden is not sure about is never checked for you, and with nothing checked Apply
   waits; the rules of a known project whose folder is gone are not offered for removal (Task 10
   `test_the_writing_review_is_a_checklist_with_not_sure`,
   `test_a_listed_project_with_a_missing_folder_keeps_its_rules`).

## Triage of the deferred findings

Sources: the ledgers of the earlier review follow-up, Parts 1–6 (F1 truth, F2 gateway contract,
F3 management, F4 speed, F5 secrets, F6 instructions), checked against the code on 2026-10-22
(`align-listing-fix`, one commit ahead of `main`), plus one item the coordinator added (47).
Rows 48–79 come from the ledgers of the visual plan's Parts 1–3, checked against `main`
(`d8c05cc`) on 2026-10-24. Lines in the raw list that are tool-call noise are left out.

"Map Part N" is Part N of `docs/superpowers/specs/2026-10-23-map-pages-design.md`, which replaced
the old Parts 4–6.

| # | Item (source) | Status | Reason |
| --- | --- | --- | --- |
| 1 | ROADMAP part-1 line got "(done)" early (F1) | already fixed | No "(done)" in `ROADMAP.md`. |
| 2 | Unreachable "Nothing in it yet." in `gatewayCardWords` (F1) | re-check after map Part 4, Task 8 | The card is replaced by the Gateway map and list (4.3, 4.5); Task 8 checks that no such dead line is left. |
| 3 | With `problem` set, the card line hides servers and clients (F1) | re-check after map Part 4, Task 8 | Task 8 checks that the gateway block and Overview show the problem beside the servers and clients. |
| 4 | No node test for no action / an old entry; no route test that `/api/overview` passes `held` and `problem` (F1) | re-check after map Part 4, Task 8 | Tests only, on the new Gateway view and Overview. |
| 5 | Scope line on tabs with no "+ Add" (F1) | already fixed | `scopeLine` checks `hasAdds(kind)`. |
| 6a | Page-words test checks only the literal (F1) | won't fix | Page-words tests pin words by design; behaviour is in node tests. |
| 6b | `library.test.mjs` shadows `row` (F1) | fix here, Task 9 | Two local `const row` in test bodies. |
| 7 | `via_gateway == KITDEN_GATEWAY` guard no test makes fail (F1) | won't fix | A cheap guard; held items carry owner `kitden` today. |
| 8a | No test for a plugin-provided `kitden` entry in findings (F1) | fix here, Task 9 | Test only. |
| 8b | Test file imports `make_home` directly (F1) | won't fix | 43 test files import from `tests.conftest`; it is the repo's pattern. |
| 9a | A held, unchanged remote server is asked by `needs_sign_in` at preview (F1) | won't fix | One request to that server's own address on a rare path; skipping it needs the Keychain read first. |
| 9b | `after.py` loop coupled to `edit.key[0]` (F1) | won't fix | No behaviour change. |
| 9c | `test_after` imports helpers from `test_local_gateway_move` (F1) | won't fix | Same pattern as `test_add_server`. |
| 10a | No way to fold back after "Show all" (F1) | re-check after map Part 4, Task 8 | Spec: "a folded group can fold back". Task 8 checks every group that still folds ("N more", List groups). |
| 10b | Fold focus test only greps strings (F1) | won't fix | Focus wiring is DOM code; the fold rule has a node test and Task 8 re-checks it. |
| 10c | ROADMAP gateway line packs two items (F1) | superseded by Part 8 | v0.3.0 notes rewrite these lines; ROADMAP is the owner's for now. |
| 11 | Focus row index 6 hard-coded (F1) | already fixed | `i === FOLD_AT`. |
| 12 | `allowed_tools` calls `strict_mode` per tool (F2) | won't fix | A dict lookup per tool. |
| 13a | Strict row words per client untested; row text not pinned (F2) | superseded by map Part 4 | 4.4: the held server's Details carries the strict review words and pins them. |
| 13b | `strict=True` in a move relies on app.py's tool read (F2) | won't fix | app.py's preview is the only caller and refuses first. |
| 14a | `views.py` imports private `_scopes` (F2) | superseded by map Part 4 | 4.2 data: `_states` and `tools_view` are rewritten into `tool_list`. |
| 14b | All-projects view: a tool ruled only in a project shows New (F2) | superseded by map Part 4 | 4.2 data: the tool's origin is "new and waiting" (strict) only where true; All projects says "On in N projects". |
| 15 | A server removed from gateway.json mid-session stays callable (F2) | already fixed | `is_allowed` refuses a server not in the file. |
| 16 | `list_changed` can be a no-op nudge (F2) | won't fix | Best effort by design; keeping it waits for a real-client check (earlier design, "Left to the builder"). |
| 17 | A tool turned off mid-session is allowed again when the file then breaks (F2) | fix here, Task 7 | Fallback is the start rules. |
| 18a | `tool_hint` computed twice per tool (F2) | already fixed | One call in `tools_view`. |
| 18b | Changes line of a batch drops on/off and gets long (F2) | fix here, Task 7 | `changeTitle` lists every tool name. |
| 18c | With state "on" (API only) the batch note says "refused at once" (F2) | won't fix | The sentence says what a switch does and when the list updates; the page offers only "off". |
| 19 | `destructiveHint: false` alone gives "unknown" (F2) | already fixed | `tool_hint`: any hint key means "writes"; Task 10 lists unknown tools under "Not sure". |
| 20a | `callsText` shows `NaN:NaN` on a broken `last` (F2) | fix here, Task 7 | On `callsText` as map Part 4 builds it in `gateway-details.js` (4.4 Calls). |
| 20b | A test sets `TZ=UTC` and never restores it (F2) | fix here, Task 7 | — |
| 20c | `count_call` chmods the folder on every call (F2) | won't fix | One cheap call keeps the folder private. |
| 20d | Forwarded calls that errored are counted (F2) | won't fix | The count is of forwarded calls, as `docs/development.md` says. |
| 21a | Long lines in README (F2) | superseded by Part 8 | README is rewritten. |
| 21b | Long lines in `docs/development.md` (F2) | fix here, Task 11 | — |
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
| 26b | "+ Add" on cells that preview refuses (F3) | superseded by Part 2 | Built in Part 2 (2.3): no "+ Add" where preview would refuse. |
| 26c | Codex `Authorization` header matched case-sensitively (F3) | fix here, Task 9 | `authorization: Bearer ${X}` is refused instead of translated. |
| 26d | `bearer_token_env_var` silently wins over an `Authorization` header (F3) | fix here, Task 9 | Refused. |
| 27a | An unclosed `${…` can echo text in a refusal (F3) | fix here, Task 9 | Checked: `${tok-SENTINEL…` is shown in the sentence. |
| 27b | A Codex literal `${X}` kept for Cursor gets no secret note (F3) | won't fix | Rare; the note follows `redact`, which reads `${X}` as a reference. |
| 28a | `addChoices` ignores its arguments (F3) | fix here, Task 9 | — |
| 28b | A project plugin install makes other projects' cells say "has it in another project" (F3) | won't fix | True words; the cell offers no Add that would fail. |
| 28c | Cursor's via and done cells also get the per-project hint (F3) | won't fix | The hint still tells how to add it to one project in Cursor; `test_cursor_plugin_cells_say_where_to_add_per_project` pins it on purpose. |
| 29a | "Not the same; not touched" beside an add of that name to a third client (F3) | superseded by map Part 5 | 5.4: the four groups, "Needs your decision". |
| 29b | Stale file changes stay visible under a disabled Apply (F3) | superseded by map Part 5 | 5.4 rebuilds the Add missing review. |
| 29c | The toast count includes deduplicated items (F3) | superseded by map Part 5 | 5.4: the review leads with "Adds N items to <project>", which sets the count. |
| 30a | No test that Add missing with Cursor importing puts a Claude Code plugin in the project and does not name Cursor (F3) | fix here, Task 5 | Test only. |
| 30b | Cursor's import note does not check Cursor already loads the plugin (F3) | fix here, Task 5 | `plugin.install` adds `CURSOR_IMPORT` without a check. |
| 31a | `fake_binary` duplicates `fake_client_command` (F4) | already fixed | No `fake_binary` left. |
| 31b | `version_cache.CLIENTS` repeats `versions._COMMANDS` keys (F4) | won't fix | Three names; no behaviour. |
| 31c | First-scan timing bound `< 1` s is tight (F4) | fix here, Task 9 | `test_the_first_scan_runs_no_version_command`. |
| 31d | `_read_version` reads the file twice per Codex scan (F4) | won't fix | One small JSON file. |
| 32a | Ctrl+C can wait for a running version command (F4) | fix here, Task 8 | Spec item. |
| 32b–e | No refresh with `first_scan_later=False`; plain path ends progress late; duplicated client mapping; one error line for refresh and rescan (F4) | won't fix | Test-only paths and log lines; the page keeps working. |
| 33 | `versions.json` missing from the data-file list (F4) | fix here, Task 11 | — |
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
| 40a | `docs/development.md` Gateways line overlong (F5) | fix here, Task 11 | — |
| 40b | README does not name "Move secrets to the Keychain…" (F5) | superseded by Part 8 | — |
| 41 | An item whose own write failed is said to "keep the new value" (F5, parked) | fix here, Task 6 | "may hold the new value". |
| 42 | A token that ends in a line break never reads back equal (F5, parked) | fix here, Task 6 | — |
| 43 | ROADMAP's Part 5 line says OAuth servers move (F5 note) | fix here, Task 11 | A line for the owner (ROADMAP is the owner's). |
| 44a | Cursor `.cursor/agents`, `.claude/agents`, `.cursor/commands`, CLAUDE.md; agent names from `name:` (F6) | fix here, Task 2 | Built only where the docs confirm. |
| 44b | Claude Code reads `AGENTS.md` when there is no `CLAUDE.md` (F6) | superseded by map Part 6 | 6.1 builds it (checked 2026-10-23 in the map spec); Task 2 does not read it. |
| 45a | Overview does not count instruction files (F6) | already fixed | `LOAD_KINDS` has instructions. |
| 45b | Two files fail `ruff format --check` (F6) | already fixed | `82fefdc`. |
| 45c | Visual check of the page on a fixture home (F6) | superseded by walkthrough 2 | The owner walks the page in `kitden demo`. |
| 46 | The watcher does not watch project folders (F6) | fix here, Task 3 | Spec item. |
| 47 | The review's After chips for turning a Claude Code user plugin on or off do not name Cursor (coordinator) | fix here, Task 5 | `cursor.py _claude_plugins` reads `enabledPlugins`; app.py's comment says only add and remove reach Cursor. |
| 48 | `sample.py` comments with other-tool facts and no date (Part 1) | fix here, Task 9 | The Cursor hash and the Codex plugin list now carry dates; "Codex does not trust this folder" and "Cursor keeps no name for it elsewhere" do not. Comment only. |
| 49 | `views/after.py _had_on` compares the pinned real `step.cwd` with the recorded project key (Part 1) | already fixed | It compares real paths (`os.path.realpath`); `test_after.py` has a link test. |
| 50 | Demo: `gateway.connect` and `gateway.switch` refusals do not say "Not part of the demo." (Part 1) | fix here, Task 9 | They say "Register the gateway first.", which the demo cannot do. |
| 51 | `DemoRunner` removing an absent entry answers 0; a real client fails (Part 1) | fix here, Task 9 | — |
| 52 | `CANNED_TOOLS` imports private `_tool` from `sample.py` (Part 1) | won't fix | Both are in `kitden.demo`; a private helper shared inside one package changes nothing. |
| 53 | Demo sweep skips `/api/projects/{id}/effective` and `/api/commands` (Part 1) | fix here, Task 9 | `_demo_outputs` in `tests/security/test_no_secrets.py` lacks both; the sentinel sweep has them. |
| 54 | `test_cli.py` `finally` may raise KeyError if main fails before the build (Part 1) | fix here, Task 9 | `test_a_folder_that_cannot_be_deleted_is_named` reads `seen["home"]` in `finally`. |
| 55 | During an Apply, `closeForProject` does nothing and `openedIn` stays old (Part 1) | won't fix | A window of under a second; `openPanel` sets `openedIn` again when Details is drawn after the Apply, as its comment says. |
| 56 | After chip "Via Kitden gateway" names the route in the chip's word slot (Part 2) | superseded by map Part 4 | S.1 passes through the state words and After chips; the Gateway's "Used by" tiles show the route. Task 9 takes it if a chip still does this. |
| 57 | The skill list reads no project, so a "Via plugin" installed cell can be wrong for a plugin installed only in another project (Part 2) | superseded by map Part 5 | 5.1 and 5.3: the tree reads what each client holds, in the picked project. |
| 58 | Skill-list "installed" cells carry no items, so they are never compared (Part 2) | superseded by map Part 5 | 5.4: Differences compares rows; a plugin row differs when a child row does. |
| 59 | Three-way tie in `odd_ones` where the reference's kind differs (Part 2) | fix here, Task 9 | Compare inside the plugin and the plain groups; map 5.4 "Needs review" uses it. |
| 60 | A copy into a nested project does not count the parent project's copies for "loads twice" (Part 2) | fix here, Task 5 | `skills_loaded`, where the client's docs confirm that it reads a parent folder's project skills. |
| 61 | A same-place Back with a panel open keeps it; the address and the panel name different items for a moment (Part 2) | superseded by map Part 4 | S.3 and S.4: selection and Details follow the address. Task 9 takes it if Part 4 leaves it. |
| 62 | `gateway.js` `save()` from "No gateway yet" does not drop a pending arrival (Part 2) | already fixed | `save()` sets `arrival.pending = false`; `test_page_words.py` pins it. |
| 63 | No test calls `followHash('#map…')` (Part 2) | fix here, Task 9 | Test only; check `OLD_VIEWS` after map Part 5 (5.2 old links). |
| 64 | Removing a project from a client's list while another file of that client stays broken keeps the project's items stale on the picker (Part 2) | won't fix | Needs two files of one client with one broken; the items say they are from the last good read and clear when the file reads again. |
| 65 | `review.js`: a late preview after Cancel still opens (Part 3, minor 4) | fix here, Task 9 | — |
| 66 | A held-server Remove names no clients (Part 3, minor 7) | fix here, Task 9 | The review's done line. |
| 67 | `routeWords` copies `load_map._route`'s order in JS; the words are pinned, the order is not (Part 3) | fix here, Task 9 | — |
| 68 | `heldRule` says "this project's switch for files is off" when every client's `kitden` entry is off and the switch is on (Part 3) | fix here, Task 9 | — |
| 69 | "Turned off in api and Codex." mixes project folders and clients (Part 3) | fix here, Task 9 | — |
| 70 | The "⌘ Enter" hint stays after Apply gives way to "Preview again" (Part 3) | fix here, Task 9 | — |
| 71 | At the 1 s mark the source line can push drawn rows down once, on the Plugins tab (Part 3) | superseded by map Part 5 | 5.2 and 5.6 replace the Plugins tab with the tree and the add panel. |
| 72 | `after.py`'s general move path shows chips only for moving clients, while Details names clients already connected to a registered gateway (Part 3) | fix here, Task 9 | — |
| 73 | A move of a Claude Code local entry names no place in the review, while Details says "In website." (Part 3) | fix here, Task 9 | Check first: `change_target` may already say it. |
| 74 | `panel.js` `cancelPreview` repeats `panelState.current` four times; a node test that loads `details.js`, `tools.js` and `review.js` each first (Part 3) | already fixed | `cancelPreview` reads it once; 'each side panel module loads first, on its own' is in `details.test.mjs`. |
| 75 | Two carried-over comments above the wrong function in `details.js` (Part 3) | fix here, Task 9 | Comment only. |
| 76 | Rows-over-header morph glitch in the Library (Part 3) | superseded by map Part 5 | 5.4 replaces the table with the tree and the List. |
| 77 | `details.js` size (about 830 lines in the ledger, 902 on `main`) (Part 3) | superseded by map Part 4 | Part 4 moves the Gateway cards into `gateway-details.js`. Task 9 splits `details.js` only if it is still over 900 lines after Part 6. |
| 78 | `design.md` length: a read-through for repetition (Part 3) | fix here, Task 11 | One read, cut repeats; no pinned word changes. |
| 79 | The frames' hint lines under the page body, and the scope bars of O1 (Overview) and C1 (Changes) (map Parts 4–6) | fix here, Task 9 | Parts 4–6 leave them out (Part 6 builds only the Instructions hint line). Words from the frames, for facts Kitden knows. |

Spec items with no line above: safer `~/.claude.json` writes (Task 4), one start read (Task 8),
the gateway card's set-up for every client (re-checked in Task 8 against map Part 4's client
block), `tests/fixtures/README.md` (Task 9), and the two items the map spec moved here from the
old Part 5: the writing-tools checklist and the rules for folders Kitden no longer finds
(Task 10).

---

### Task 1: Walkthrough 2 fixes (the controller fills this task)

**Files:** set by each ruling. For the first-view rule (Step 4): `src/kitden/web/static/js/store.js`
(`viewMode`), `docs/design.md`, `tests/frontend/store.test.mjs`.

**Interfaces:**
- Consumes: the results file `docs/research/walkthrough-<date>.md` (map Part 6's script, the
  owner's answers); map Part 4's `viewMode(state, count) -> "map" | "list"` and `MAP_AT = 15` in
  `store.js` (the master plan's "Names that cross part boundaries"), and the hash `view=map|list`.
- Produces: nothing new. If the owner finds that a map page does not help, that page's first view
  becomes List: one rule in `viewMode`, no new setting. The map stays behind the Map | List switch.

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

- [ ] **Step 4 (only if the owner found that a map page does not help): List is that page's first
  view.** Test first (the field that holds `view=map|list` is map Part 4's name):

```js
// tests/frontend/store.test.mjs (viewMode from store.js)
test('a page the owner found no help in opens in List, and an address with view=map still opens the map', () => {
  // for that page: no choice in the address, 3 blocks → 'list'; the address says view=map → 'map'
  // for every other page: no choice, 3 blocks → 'map'; 16 blocks → 'list' (MAP_AT)
});
```

  Implement: `viewMode` answers `"list"` for that page when the address holds no choice. Nothing
  else in the map code changes. `docs/design.md`: the Map or List row names the page that opens in
  List after walkthrough 2. The part's report tells Part 8: "the tour stop for <page> sets
  `view=map`".
  Commit: `Pages: <page> opens in List after the walkthrough`.

---

### Task 2: What clients read: Cursor's agents and agent names (picture gaps)

**Files:**
- Modify: `src/kitden/clients/base.py` (gains `front_matter`, moved from `views/skills.py`, and
  `agent_items`), `src/kitden/views/skills.py` (imports `front_matter` back from `base.py`),
  `src/kitden/clients/claude_code.py` (`_instruction_files`: agents named by `name:`),
  `src/kitden/clients/cursor.py` (user and project scan)
- Create fixtures: `tests/fixtures/claude_code/2.1.283/home/.claude/agents/team/lead-file.md`
  (`name: lead`, `description: Leads`), `.../home/.claude/agents/notes.md` (no front matter),
  `tests/fixtures/cursor/3.21.16/home/.cursor/agents/planner.md` (no `name`),
  `tests/fixtures/cursor/3.21.16/home/work/site/.cursor/agents/tester.md` (`name: site-tester`)
- Test: `tests/unit/test_read_claude_code.py`, `tests/unit/test_read_cursor.py`,
  `tests/unit/test_library.py` (instruction rows that count every item)
- Not here: Claude Code's `AGENTS.md` without a `CLAUDE.md` is map Part 6 (6.1, row 44b).

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
  - code.claude.com/docs/en/sub-agents: `name` and `description` are required; a file without
    `name` is skipped; the name comes only from `name:`, not the file or its sub-folder.

- [ ] **Step 2: Write the failing tests**

```python
def test_claude_code_names_an_agent_by_its_name_field_and_skips_one_without(tmp_path, no_version):
    home = make_home(tmp_path, "claude_code/2.1.283")
    agents = {i.name for i in ClaudeCodeAdapter(home).scan().items
              if i.kind is ItemKind.INSTRUCTIONS and dict(i.summary)["category"] == "agent"}
    assert agents == {"reviewer", "lead"}  # not "team:lead-file"; notes.md has no name


def test_cursor_reads_agents_from_its_folders_and_claude_codes(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    found = {(i.scope, i.name, i.source.owner_client) for i in CursorAdapter(home).scan().items
             if i.kind is ItemKind.INSTRUCTIONS and dict(i.summary)["category"] == "agent"}
    assert found == {(Scope.USER, "planner", "cursor"), (Scope.USER, "reviewer", "claude_code"),
                     (Scope.USER, "notes", "claude_code"), (Scope.PROJECT, "site-tester", "cursor")}
```

- [ ] **Step 3: Run them to see them fail**: `uv run pytest tests/unit/test_read_claude_code.py tests/unit/test_read_cursor.py -v`.
- [ ] **Step 4: Implement.** Claude Code: agents through `agent_items(..., recursive=True, needs_name=True)`
  in both folders (skip a home-folder project's `.claude` files, as today). Cursor:
  `agent_items(..., recursive=False, needs_name=False)` for each of its six folders; `.claude/...` and `.codex/...` folders are `SourceKind.OTHER_CLIENT_FOLDER`
  owned by `claude_code` and `codex`. Each location gets its `# checked <date> (<url>)` comment.
  Update the expected sets of the read and library tests that count every item.
- [ ] **Step 5: Run** the two files and `uv run pytest tests/unit/test_library.py tests/unit/test_mcp_server.py tests/unit/test_demo_home.py tests/security -v` → PASS. (Part 1's sample agent `~/.claude/agents/reviewer.md` has `name: reviewer` and a description, so its contract test still finds it. Cursor now also lists it through `~/.claude/agents`: if that moves the medium count out of Part 1's 50–75 range, widen the range in `test_demo_home.py` in this commit.)
- [ ] **Step 6: Run all checks**, then commit

```bash
git add src/kitden/clients/base.py src/kitden/clients/claude_code.py src/kitden/clients/cursor.py src/kitden/views/skills.py tests/fixtures/claude_code/2.1.283/home/.claude/agents tests/fixtures/cursor/3.21.16/home/.cursor/agents tests/fixtures/cursor/3.21.16/home/work/site/.cursor/agents tests/unit/test_read_claude_code.py tests/unit/test_read_cursor.py tests/unit/test_library.py
git commit -m "Instructions: Cursor's agents; Claude Code's agents by name"
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
- Consumes: the words of `views/words.py STATE_WORDS` where it has them ("on" says "On" since
  map Part 4).
- Produces:
  - `skills_loaded(inventory, skills: list[dict], project: str | None) -> dict[str, set[str]]`:
    client → names of the skills it loads now in `project`: its user and plugin skills that are
    not off, its skills of that project, and the clients a skill-list row's `installed` names.
    For a project inside another known project, the skills of the parent project count too
    where the client's docs say it reads them (row 60; `# checked <date> (<url>)` per client,
    else "not checked" and not counted).
  - `after_words(change, inventory, cursor_imports=False, skills=None, home=None, project: str | None = None)`.
  - Cursor entries in the After chips when Cursor imports Claude Code's plugins and the step is a
    Claude Code user plugin:
    - `plugin.disable`, Cursor has no other copy: `{"client": "cursor", "state": "off", "word": "Off", "note": "Cursor loads Claude Code plugins, so it turns this one off too."}`
    - `plugin.disable`, Cursor keeps another copy: `{"client": "cursor", "state": "on", "word": "Loads once", "note": "Cursor loads Claude Code plugins, so it turns this copy off and keeps {its own | the other Claude Code copy}."}`
    - `plugin.enable`, no other copy: `{"client": "cursor", "state": "on", "word": STATE_WORDS["on"], "note": "Cursor loads Claude Code plugins, so it turns this one on too."}`
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


def test_a_copy_into_a_nested_project_counts_the_parent_projects_copies(home):
    # work/api holds a project skill Cursor loads; work/api/tools is a known project inside it;
    # Add missing for a Claude Code copy into work/api/tools: its listing["will_add"] entry has
    # note "Cursor would load it twice." and chosen False (only for a client whose docs say it
    # reads the parent folder's skills: the test names that client)


def test_installing_a_claude_code_plugin_cursor_has_says_cursor_loads_it_twice():
    # Cursor's own notes@cursor-mkt is on → the Cursor entry is "Loads twice" with "and its own."
```

  (`imported(name)` is a new helper: a Cursor plugin item with `SourceKind.OTHER_CLIENT_FOLDER`,
  owner `claude_code`.)

```python
def test_add_missing_and_its_review_agree_on_a_project_skill_loaded_twice(home):
    # work/api: a project skill Cursor loads (in the project folder Cursor's adapter reads) that
    # Claude Code lacks; the Claude Code add's copy reaches Cursor:
    # its listing["will_add"] entry (map Part 5, 5.4) has note "Cursor would load it twice." and chosen False;
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
  (new `putBackClients`, beside `heldActions`), `src/kitden/web/static/js/gateway-details.js`
  (`heldCard` passes `putBackClients(...)` to `heldActions`; `callsText`)
- Test: `tests/unit/test_local_gateway_settings.py`, `tests/unit/test_local_gateway_proxy.py`,
  `tests/unit/test_local_gateway_views.py`, `tests/unit/test_after.py`,
  `tests/frontend/parts.test.mjs`, `tests/frontend/details.test.mjs` (`putBackClients`),
  `tests/frontend/gateway-details.test.mjs` (the new `callsText` case),
  `tests/frontend/panel.test.mjs` (the `TZ` fix in 'calls text says how many and when', or
  wherever map Part 4 left that test)

**Interfaces:**
- Consumes: map Part 4's `callsText(calls, now)` in `gateway-details.js` ("12 calls · last today
  14:02", map spec 4.4; carried over from the old Part 5).
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
// gateway-details.test.mjs (callsText from gateway-details.js)
test('a call time that cannot be read shows the count alone', () => {
  assert.equal(callsText({ count: 3, last: 'nope' }, new Date()), '3 calls');
});
```

  The test that sets `process.env.TZ = 'UTC'` keeps the old value and puts it back in a `finally`
  (deleting it when it was unset). `parts.test.mjs` pins today's batch line
  ('Changed the rules for create_issue, delete_issue · Kitden gateway'): it takes the new words.
  The `heldActions` tests and `test_page_words.py`'s "Put back in" pin stay as they are.
- [ ] **Step 2: Run them to see them fail** (`uv run pytest tests/unit/test_local_gateway_settings.py tests/unit/test_local_gateway_proxy.py tests/unit/test_local_gateway_views.py tests/unit/test_after.py -v`, `node --test tests/frontend/*.test.mjs`).
- [ ] **Step 3: Implement.** The held server's Details (`heldCard` in `gateway-details.js`, map
  Part 4, 4.4) reads `/api/explain` for the server's name before it draws its buttons, so it has
  the definitions `putBackClients` needs.
- [ ] **Step 4: Run** the same commands → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/local_gateway/settings.py src/kitden/local_gateway/proxy.py src/kitden/local_gateway/views.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/parts.js src/kitden/web/static/js/details.js src/kitden/web/static/js/gateway-details.js tests/unit/test_local_gateway_settings.py tests/unit/test_local_gateway_proxy.py tests/unit/test_local_gateway_views.py tests/unit/test_after.py tests/frontend/parts.test.mjs tests/frontend/details.test.mjs tests/frontend/gateway-details.test.mjs tests/frontend/panel.test.mjs
git commit -m "Gateway: the last good rules decide; Put back only where it works" -m "The Changes line of a batch says on or off."
```

---

### Task 8: Page: one start read, a quick stop, and the gateway re-check

**Files:**
- Modify: `src/kitden/web/static/js/app.js` (`start`), `src/kitden/clients/version_cache.py`
  (`run_version_command`, new `stop_version_commands`), `src/kitden/web/app.py` (`lifespan`)
- Re-check only (fix where the same defect is found, with `docs/design.md` in the same commit):
  the Gateway pages and Overview as map Parts 4 and 6 leave them
- Test: `tests/unit/test_page_words.py`, `tests/unit/test_version_cache.py`; for the re-check, the
  test files of map Parts 4 and 6 for those pages (such as `tests/frontend/gateway.test.mjs`,
  `tests/frontend/overview.test.mjs`, `tests/unit/test_overview.py`)

**Interfaces:**
- Consumes: Part 2 Task 6's handling of a project no longer on the list: `loadShared` no longer
  resets the project, and `reload()` (which calls `loadShared` first) reads no project data while
  `projectGone()`. So `start()` no longer needs its own early `loadShared()` call: it calls
  `refresh()` only, and the start reads `/api/clients`, `/api/projects` and `/api/changes` once.
  `loadShared` stays exported from `store.js` (`reload()` and Part 8's tour call it).
- Produces: `version_cache.stop_version_commands() -> None`: kills every version command still
  running; `run_version_command` then returns None. `lifespan` calls it before it waits for its
  tasks.

**The gateway re-check (rows 2, 3, 4, 10a and the gateway card's set-up for every client).** The
old Gateway card is gone: map Part 4 replaces it with the Gateway map and list, a client block
(`clientCard`: "Set up in <client>…", 4.4) and a gateway block (`gatewayCard`), and map Part 6 replaces the Overview gateway
card. Check each item below against `main`. If the defect is not there, close it with one line in
the report. If it is, fix it with the test shown, written for the new code:

- Row 2: the unreachable branch is gone: no code path draws "Nothing in it yet." for a gateway
  with nothing in it. Node test: the gateway block of `gatewayTree` and `gatewayCard` for a
  gateway with `servers: 0` and `clients: []` hold no such line. This is not a ban on the words
  elsewhere (map Part 6 uses "No servers yet." on Overview and pins it).
- Row 3: with a settings problem, the gateway block and Overview show the servers and clients
  and the problem beside them, not instead of them. Node test: the model for a gateway with
  `clients: ['cursor']` and `problem: 'Kitden could not read the gateway settings.'` has the
  Cursor block and the problem text.
- Row 4: `test_the_gateway_view_passes_held_servers_and_the_problem`: a home with a held server and
  a broken `gateway.json`; `/api/gateway-view` and `/api/overview` carry
  `"problem": "Kitden could not read the gateway settings."`; with a good file, one server.
  Node test: a client with an old `kitden` entry is not offered "Set up in <client>…".
- Row 10a: a group that still folds with "Show all N" folds back with a quiet "Show fewer"
  (`btn small ghost`), and focus goes to its "Show all N" button (the existing `show:${key}` focus
  key). Node test on the fold rule: 7 rows, open → all shown and `fewer` true; closed → 6 shown
  and 1 cut; 6 rows, open → `fewer` false. `test_an_open_group_folds_back`:
  `'"Show fewer"'` is in the page file that draws the fold.
- Set-up for every client: `clientCard` (`gateway-details.js`) is checked once per found client.
  Each client without the `kitden` entry has the action "Set up in <client>…"; a client with an
  old or turned-off entry does not. Node test in `gateway-details.test.mjs`: with `codex` and
  `cursor` lacking it and `claude_code` having it, the three cards' "Set up in …" actions are
  `['Set up in Codex…']`, `['Set up in Cursor…']` and none.

- [ ] **Step 1: Write the failing tests** for the start read and the stop, then run the re-check
  and write a failing test for each defect still there.

```python
def test_the_start_reads_shared_data_once():
    assert "loadShared" not in script("app.js")


def test_stopping_the_page_does_not_wait_for_a_version_command(tmp_path, monkeypatch):
    # a fake client command that writes a marker, then `exec sleep 30`; version_command patched to it;
    # create_app(build, token, port, version_refresh=lambda: {"cursor": run_version_command("cursor")},
    #            first_scan_later=True, quick_first=True)
    # with TestClient(app): wait for the marker; leaving the block takes under 3 s


def test_stop_version_commands_ends_a_running_one(tmp_path, monkeypatch):
    # run_version_command in a thread; after the marker, stop_version_commands(); the thread
    # ends within 2 s and the answer is None
```

- [ ] **Step 2: Run them to see them fail** (`node --test tests/frontend/*.test.mjs`, `uv run pytest tests/unit/test_page_words.py tests/unit/test_version_cache.py -v`).
- [ ] **Step 3: Implement.** `start()` calls `refresh()` only. `run_version_command` runs the
  command with `subprocess.Popen` (looked up at call time, so the test guard still applies) and
  keeps it in a set under a lock until it ends. For a re-check fix: the line in `docs/design.md`
  that describes it (a fold that folds back; "Set up in <client>…" for each client without the
  entry; a settings problem beside the servers and clients).
- [ ] **Step 4: Run** the same commands → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/web/static/js/app.js src/kitden/clients/version_cache.py src/kitden/web/app.py tests/unit/test_page_words.py tests/unit/test_version_cache.py
git commit -m "Page: read shared data once at start" -m "Ctrl+C no longer waits for a client's version command."
```

(Stage the files of a re-check fix by name in the same commit, and add a third line to the
message: "The gateway pages fold back and show a problem beside the rest.")

---

### Task 9: Small items: copied entries, tests, the fixtures README and the Parts 1–3 minors

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

**Second commit: the Parts 1–3 minors (rows 48–78).** Check each row against `main` first (Global
Constraints). A row already fixed is closed with one line; a test-only row that passes at once is
said so; a row marked "superseded by map Part N" is fixed here only if map Part N left it.

**Files (second commit):**
- Modify: `src/kitden/demo/sample.py` (two comments, row 48), `src/kitden/demo/runner.py` (row 51),
  `src/kitden/web/app.py` (the demo's gateway refusals, row 50), `src/kitden/views/match.py`
  (`odd_ones`, row 59), `src/kitden/views/after.py` (the move's After list, row 72),
  `src/kitden/web/static/js/panel.js` and `review.js` (`review`, `closePanel`, `changeWords`, the
  apply hint; rows 65, 66, 70), `src/kitden/web/static/js/details.js` (`routeWords`, `heldRule`,
  `whyParts`, two comments; rows 67–69, 75, 77)
- Test: `tests/unit/test_demo_mode.py`, `tests/unit/test_demo_stand_ins.py`,
  `tests/security/test_no_secrets.py`, `tests/unit/test_cli.py`, `tests/unit/test_match.py`,
  `tests/unit/test_after.py`, `tests/unit/test_review_scope.py`, `tests/unit/test_page_words.py`,
  `tests/frontend/context.test.mjs`, `tests/frontend/review.test.mjs`,
  `tests/frontend/details.test.mjs`

- [ ] **Step 6: Write the failing tests**

```python
# tests/unit/test_demo_mode.py (row 50)
def test_a_gateway_connect_or_switch_in_the_demo_says_it_is_not_part_of_the_demo(tmp_path):
    # demo_page(tmp_path); preview "gateway.connect" and "gateway.switch" with targets
    # [{"client": "cursor"}] and params {"gateway": "none", "name": "files"}: both answer 422
    # with {"detail": NOT_IN_DEMO}, not "Register the gateway first."


# tests/unit/test_demo_stand_ins.py (row 51)
def test_the_runner_fails_to_remove_an_entry_that_is_not_there(tmp_path):
    home = build_demo_home(tmp_path, "small")
    before = _files(tmp_path)
    assert DemoRunner(home)(["claude", "mcp", "remove", "-s", "user", "nope"], None).returncode == 1
    assert _files(tmp_path) == before


# tests/unit/test_match.py (row 59)
def test_a_tie_with_a_plugin_reference_still_compares_the_plain_folders():
    plugin = frozenset({"d1", "plugin:p@m"})
    keys = {"claude_code": plugin, "codex": frozenset({"d2"}), "cursor": frozenset({"d3"})}
    assert odd_ones(keys) == {"cursor"}  # codex is the reference of the plain group


# tests/unit/test_after.py (row 72)
def test_a_move_names_a_client_already_on_a_registered_gateway():
    # a server moved into the Kitden gateway that Cursor already reaches through a registered
    # gateway: the After list has a Cursor entry that says so, in the words Details uses


# tests/unit/test_review_scope.py (row 73)
def test_a_move_of_a_local_entry_names_its_project_in_the_review():
    # a Claude Code local entry (Scope.LOCAL, project website) moved into the Kitden gateway:
    # change_target(...) is {"scope": "project", "project": website, "others_unchanged": ...}
```

  Test-only rows, passing at once: row 53 (`_demo_outputs` in `tests/security/test_no_secrets.py`
  also reads `/api/projects/{id}/effective` for each project and `/api/commands?item={id}` for
  each item) and row 54 (`test_a_folder_that_cannot_be_deleted_is_named` deletes the folder in
  `finally` only `if "home" in seen`).

```js
// tests/frontend/context.test.mjs (row 63)
test('an old #map address opens the Library', () => {
  followHash('#map?project=a&q=git');
  assert.equal(state.view, 'library');
  assert.equal(state.q, 'git');
});
// tests/frontend/review.test.mjs
test('a preview that answers after the panel was closed opens nothing and is cancelled', async () => {
  // row 65: review(...) waits for its preview; closePanel() runs (Cancel or Escape); the answer
  // comes: no review is drawn (panelState.current stays null) and POST /api/changes/<id>/cancel
  // is sent once
});
test('a held-server Remove names the clients that lose it in its done line', () => {
  const change = { action: 'gateway.remove', steps: [{ client: 'kitden', name: 'github' }], after: [{ client: 'claude_code' }, { client: 'cursor' }] };
  assert.equal(changeWords(change, { params: { server: 'github' } }).done, 'Removed github from the Kitden gateway · Claude Code and Cursor lose it');
  assert.equal(changeWords({ ...change, after: [{ note: 'github is then in no client.' }] }, { params: { server: 'github' } }).done, 'Removed github from the Kitden gateway'); // row 66
});
// row 70: extend 'settings changed since the preview: the callout comes first and Apply gives way
// to Preview again': the apply-key hint ('⌘ Enter to apply' or 'Ctrl Enter to apply') is gone.
// tests/frontend/details.test.mjs (import routeWords from details.js, ROUTE_WORDS from parts.js)
test('routeWords picks the Desktop app, then the Kitden gateway, then the folder owner, then a plugin', () => {
  assert.equal(routeWords(def({ client: 'claude_desktop_code_tab', via_gateway: 'kitden' })), ROUTE_WORDS.desktop);
  assert.equal(routeWords(def({ client: 'cursor', via_gateway: 'kitden', owner_client: 'claude_code' })), ROUTE_WORDS.kitden);
  assert.equal(routeWords(def({ client: 'cursor', owner_client: 'claude_code' })), "through Claude Code's folder");
  assert.equal(routeWords(def({ client: 'codex', scope: 'plugin' })), ROUTE_WORDS.plugin);
  assert.equal(routeWords(def({ client: 'codex' })), null); // row 67; the same four cases belong in test_load_map.py
});
test('the switch sentence is not said when the kitden entries are what is off', () => {
  // row 68: the held definitions of 'two definitions that come the same way…' with the project's
  // switch on and each client's kitden entry off: no line of whyLines(...) has 'switch for files is off'
});
test('Turned off keeps clients and project folders in separate sentences', () => {
  const api = '/Users/me/work/api';
  const defs = [def({ client: 'claude_code', scope: 'project', project: api, loads: false, enabled: 'off' }), def({ client: 'codex', loads: false, enabled: 'off' })];
  assert.deepEqual(whyLines(defs, site), ['Turned off in Codex. Turned off in api.']); // row 69
});
```

```python
# tests/unit/test_page_words.py: the words of rows 66, 68 and 69 are pinned
def test_the_small_fixes_keep_their_words():
    assert "lose it" in script("review.js")
    assert "Turned off in " in script("details.js")
```

- [ ] **Step 7: Run them to see them fail** (`uv run pytest tests/unit/test_demo_mode.py tests/unit/test_demo_stand_ins.py tests/unit/test_match.py tests/unit/test_after.py tests/unit/test_review_scope.py tests/unit/test_page_words.py -v`, `node --test tests/frontend/*.test.mjs`). The test-only rows pass at once: say so.
- [ ] **Step 8: Implement.**
  - Row 48: the two comments get `# checked <date> (<where>)`, or "not checked".
  - Row 50: in the demo, `GATEWAY_CONNECT` and `GATEWAY_SWITCH` answer `stand_ins.NOT_IN_DEMO`
    (422) before the "Register the gateway first." check.
  - Row 51: `DemoRunner` removing a key that is not there answers `CommandResult(1, "Not found.")`
    and writes nothing. Only Claude Code's `mcp remove` is pinned; Codex's behaviour is "not
    checked".
  - Row 59: `odd_ones` splits the clients by `_from_plugin` and applies today's rule inside each
    group.
  - Row 65: `review()` takes a ticket that `closePanel()` and a newer `review()` change; a late
    answer cancels its preview on the server and draws nothing.
  - Row 66: `changeWords` for `gateway.remove` appends ` · {clients} lose it` from the clients in
    `change.after`; nothing when none is named.
  - Row 67: `routeWords` is exported; no change to its order.
  - Row 68: `heldRule` says the switch is off only when the winning definition is off because of the
    project's switch. If a definition cannot tell the switch from the client's `kitden` entry,
    `explain` adds the cause to it.
  - Row 69: `whyParts` writes `Turned off in {clients}.` and `Turned off in {folders}.` as two
    sentences, clients first.
  - Row 70: the apply-key hint is removed when Apply gives way to Preview again.
  - Row 72: the move's After list also has an entry for each client that reaches the server
    through a registered gateway, with Details' words.
  - Row 73: only if the test fails, `change_target` / `step_project` treat a local-scope move as a
    step in its project.
  - Row 75: the two comments move to the functions they describe. No test.
  - Row 77: only if `details.js` is still over 900 lines after Part 6 (map Part 4 moves the
    Gateway cards to `gateway-details.js`), split off its largest group of builders into a new
    module with no change in behaviour, and add that module to the list of 'each side panel
    module loads first, on its own'.
- [ ] **Step 9: Run** the files above and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 10: Run all checks**, then commit

```bash
git add src/kitden/demo/sample.py src/kitden/demo/runner.py src/kitden/web/app.py src/kitden/views/match.py src/kitden/views/after.py src/kitden/web/static/js/panel.js src/kitden/web/static/js/review.js src/kitden/web/static/js/details.js tests/unit/test_demo_mode.py tests/unit/test_demo_stand_ins.py tests/security/test_no_secrets.py tests/unit/test_cli.py tests/unit/test_match.py tests/unit/test_after.py tests/unit/test_review_scope.py tests/unit/test_page_words.py tests/frontend/context.test.mjs tests/frontend/review.test.mjs tests/frontend/details.test.mjs
git commit -m "Small fixes from the earlier parts' reviews" -m "Demo refusals, a late preview, and wording in Review and Details."
```

(Add the new module only when Step 8 split `details.js`.)

**Third commit: the frames' hint lines and scope bars (row 79).**

- [ ] **Step 11: Read the words.** The frames are in `design/kitden.pen`; read them with the
  pencil tools (read only: the owner's files are never edited or staged) and in
  `docs/research/visual-redesign-final-2026-10-23.md`. List each hint line under a page body and
  the scope bars of O1 ("All projects · 3 clients · …") and C1 ("5 changes this week") with the
  page each belongs to, and write the list into the report. Build only what Kitden knows: the
  counts of clients, projects and the changes of the last 7 days, and the project picked. A name
  Kitden does not know (such as "demo workspace") is left out, and the report says so. The
  Instructions hint line is Part 6's and is not built again.
- [ ] **Step 12: Write the failing tests**: a node test for each scope bar's pure helper (the
  frame's line with its numbers filled in; for example `5 changes this week` counted from the
  Changes list and `now`; with 1 change, the singular), and
  `test_the_frames_hint_lines_and_scope_bars_have_their_words` in `test_page_words.py`: each
  line's text is in the page file that draws it.
- [ ] **Step 13: Implement** as quiet lines (`--ink-3`, no new colour), one per page, under the
  page head or body as the frame has them; `docs/design.md` in the same commit. **Run** the two
  test commands → PASS.
- [ ] **Step 14: Run all checks**, then commit the page files that draw them (by name), their node
  test files, `docs/design.md` and `tests/unit/test_page_words.py`:

```bash
git commit -m "Pages: the frames' hint lines and scope bars"
```

---

### Task 10: Writing-tools checklist, and rules for folders Kitden no longer finds

These two items moved here from the old Part 5 (map spec, "What changes" and "Order"). Their old
design is Tasks 4 and 5 of `docs/superpowers/plans/2026-10-22-visual-part5-access.md` in git at
`d8c05cc`; the names and tests below are theirs where they still fit. Tools say **On** and
**Off** (owner, 2026-10-23), never "Allowed" or "Blocked". Check each item against `main` first
(Global Constraints).

**Where they live.** The checklist is the review that "Turn off every writing tool…" opens in the
held server's Details (`heldCard` in `gateway-details.js`, map Part 4, 4.4; the button stays
there). The list of rules for folders Kitden no longer finds is a quiet group in the Kitden
gateway block's Details (`gatewayCard` in `gateway-details.js`; 4.4 gives that block "clients,
servers and rules"): those rules belong to the gateway, not to one server.

**Files:**
- Modify: `src/kitden/local_gateway/views.py` (new `writing_checklist`, `lost_rules`, `forget_steps`)
- Modify: `src/kitden/changes/actions.py` (`GATEWAY_FORGET = "gateway.forget"  # the rules of a folder no client lists as a project leave the settings`)
- Modify: `src/kitden/views/gateway_view.py` (`gateway_view(..., lost: list[dict] | None = None)`)
- Modify: `src/kitden/web/app.py` (`preview`: the `GATEWAY_RULES` answer gains `checklist`, and a new `GATEWAY_FORGET` branch; `_gateway_view` passes `lost`)
- Modify: `src/kitden/views/after.py` (new `_forget_words`; `after_words` dispatches to it; the batch note keeps the token advice and ends with `AT_ONCE`)
- Modify: `src/kitden/web/static/js/review.js` (new `checklistGroups`, `chosenTools`, `checklistSection`; `showReview` appends it when `change.checklist`; `changeWords` title and done, `DONE_WORDS`, and `gateway.forget` added to `PLACE_IN_TITLE`, since the title names its folder)
- Modify: `src/kitden/web/static/js/gateway-details.js` (`gatewayCard`: the group of lost-folder rules, `lostRules(gateway)`), `src/kitden/web/static/js/parts.js` (`ACTION_WORDS`, `changeTitle`)
- Modify: `docs/design.md` (the Gateway section: a "Writing tools review" row, and the rules for lost folders)
- Test: `tests/unit/test_local_gateway_views.py` (its helpers `hold`, `echo`, `add_kitden`, `tool`, `project`, `page_for`; import `save_tools`, `load_settings`, `data_dir`, `SETTINGS_FILE`, `POST`, `FILES` as the old tests did), `tests/frontend/review.test.mjs`, `tests/frontend/gateway-details.test.mjs`, `tests/frontend/parts.test.mjs`, `tests/unit/test_page_words.py` (`gw()` reads `gateway.js` and `gateway-details.js`)

**Interfaces:**
- Consumes: Task 7's `rule_of` and `changeTitle` for `gateway.rules`; map Part 4's tool states (a
  tool of a server that is off is off) and the button's `params.tools` (the writing tools that are
  on now); `state_in`, `tool_hint` and `_chain`. The pattern of Add missing's chosen keys
  (`alignSection` in `review.js`): a changed box cancels this preview and asks again with the new
  choice; with nothing chosen there is nothing to preview and Apply waits.
- Produces (A, the checklist):
  - `writing_checklist(settings: dict, tools: dict, server: str, chain: list[str], chosen: list[str]) -> list[dict]`:
    in cache order, every tool of `server` that is on along `chain` (`state_in`) and whose
    `tool_hint` is not "reads", plus any tool in `chosen`; each
    `{"name", "hint", "hint_from", "chosen": name in chosen}`. A tool of a server that is off is
    off, so it is not listed.
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
  - The review keeps the token advice ("For a real guarantee, give {server} a token that can only
    read.") and says a call already running is not stopped: its note ends with `AT_ONCE`, "A tool
    turned off is refused at once; a call already running is not stopped. The client shows the new
    list in a new session." (If `after.py` on `main` lacks the running-call sentence, add it
    here.)
- Produces (B, the lost-folder rules):
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
    not empty (as `problem`), so the exact dicts in `test_local_gateway_views.py` stay. (Map
    Part 4 keeps the Kitden gateway's dict; if it renamed the key, use its name.)
  - `_forget_words(change) -> [{"note": f"No client lists {folder} as a project now, so these rules apply in no session."}]`.
  - Page: a quiet group in `gatewayCard` after its Facts (its `more` group or `after` node,
    whichever Part 4's `detailsCard` offers): `` `Rules for folders Kitden no longer finds · ${n}` ``,
    one row each: the folder in mono (its full path only as hover text), its servers as quiet
    text, and `"Remove…"` →
    `review({ action: "gateway.forget", targets: [], params: { folder: rule.path } })`.
    Review title `` `Remove the rules for ${folder}` ``, done `` `Removed the rules for ${folder}` ``,
    with no scope words after them (the preview's `target` is `"all"` for this settings step, and
    `changeWords` would add " for all projects"; `PLACE_IN_TITLE` stops that);
    the Changes line `` `Removed the rules for ${name} · Kitden gateway` ``.

**A. The checklist**

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


def test_the_checklist_leaves_out_every_tool_of_a_server_that_is_off(home):
    # hold github with its server off for all projects, tools create_issue and wipe cached:
    # writing_checklist(settings, tools, "github", [], []) == []  (a tool of a server that is off is off)


def test_the_writing_review_keeps_the_token_advice_and_says_a_running_call_is_not_stopped(home):
    # the preview's after note for a gateway.rules batch (state off) holds
    # GUARANTEE.format(server="github") and "a call already running is not stopped"


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
    assert "Turn off every writing tool…" in script("gateway-details.js")
```

- [ ] **Step 2: Run them to see them fail**.
- [ ] **Step 3: Implement**. `docs/design.md` row "Writing tools review": tools that write or may
  write are checked, each with where its hint comes from; tools Kitden is not sure about are
  listed unchecked under "Not sure"; a change previews again; with none checked, Apply waits; the
  review keeps the token advice and says a running call is not stopped.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_local_gateway_views.py tests/unit/test_page_words.py tests/unit/test_after.py -v` and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/local_gateway/views.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/review.js docs/design.md tests/unit/test_local_gateway_views.py tests/unit/test_after.py tests/frontend/review.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: the writing tools review is a checklist with Not sure"
```

**B. Rules for folders Kitden no longer finds**

- [ ] **Step 6: Write the failing tests**

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

```js
// gateway-details.test.mjs (gatewayCard from gateway-details.js)
test('the gateway block lists rules for folders Kitden no longer finds, each with Remove', () => {
  // a Kitden gateway with lost_rules [{ path: '/Users/me/work/old-site', folder: 'old-site', servers: ['echo', 'files'] }]:
  // the card has a group 'Rules for folders Kitden no longer finds · 1' with one row for old-site
  // whose Remove… action has the body { action: 'gateway.forget', targets: [], params: { folder: '/Users/me/work/old-site' } };
  // without lost_rules the card has no such group
});
```

```python
def test_the_gateway_block_lists_rules_for_folders_it_no_longer_finds():
    text = script("gateway-details.js")
    assert "Rules for folders Kitden no longer finds · ${" in text
    assert 'action: "gateway.forget"' in text and '"Remove…"' in text
```

- [ ] **Step 7: Run them to see them fail**.
- [ ] **Step 8: Implement**. `docs/design.md`: the gateway block's Details lists rules for a folder
  no client lists in a quiet group "Rules for folders Kitden no longer finds", each with the
  folder, its servers and "Remove…" (a review with Undo).
- [ ] **Step 9: Run** `uv run pytest tests/unit/test_local_gateway_views.py tests/unit/test_page_words.py tests/unit/test_after.py tests/security -v` and `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 10: Run all checks**, then commit

```bash
git add src/kitden/changes/actions.py src/kitden/local_gateway/views.py src/kitden/views/gateway_view.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/gateway-details.js src/kitden/web/static/js/review.js src/kitden/web/static/js/parts.js docs/design.md tests/unit/test_local_gateway_views.py tests/frontend/review.test.mjs tests/frontend/gateway-details.test.mjs tests/frontend/parts.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: remove rules for folders Kitden no longer finds"
```

---

### Task 11: Docs and roadmap for Part 7

**Files:**
- Modify: `docs/development.md`, `docs/design.md` (read through once),
  `tests/unit/test_docs_words.py`; `ROADMAP.md` only under the rule below. `README.md`: no change unless a sentence became false (Part 8 rewrites it).

- [ ] **Step 1: `docs/development.md`.** Gateways: "if the file cannot be read, the last rules it
  read apply"; a Keychain reference may carry `"hex": true` (a value with a line break or a
  non-ASCII letter is kept as hex text); Kitden's data folder also holds `versions.json` (see
  Speed); wrap the paragraph at 100 characters. Release hand check: the `-w` step (find it by
  its words) becomes "a token with a line break or a non-ASCII letter moves in; the server gets it unchanged"; two
  new steps, numbered after the last existing step (Parts 4–6 add steps too; count then):
  "Cursor's agent list shows an agent from `~/.claude/agents`, and the Library shows Cursor has
  it", and "Change a known project's `.mcp.json` while the page runs; the page shows it within a
  few seconds." Mark both "Not run yet". Then read `docs/design.md` through once and cut
  repeated lines (row 78); no word pinned in `test_page_words.py` changes.
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
  - **Agents:** the Instructions tab shows the agents Cursor reads from `.claude/agents`.
  - **Gateway:** the writing-tools review is a checklist with a "Not sure" group; rules for
    folders Kitden no longer finds can be removed, with Undo.
  - **Fixes:** a tool turned off stays refused when the rules file breaks; the Changes page says on
    or off for a batch; Put back only where it works; tokens with a line break move into the
    Keychain; a gateway group folds back; Ctrl+C stops at once.
  - For the owner: the "## Planned" Part 5 line says OAuth servers move; they stay direct (5.3
    waits for the owner).
- [ ] **Step 4: Run all checks**, then commit

```bash
git add docs/development.md docs/design.md tests/unit/test_docs_words.py
git commit -m "Docs: Part 7 leftovers"
```

---

## Builder calls (decisions the spec does not settle)

- Builder call: if the owner finds that a map page does not help, that page opens in List when the address holds no choice (one rule in `viewMode`); the map stays behind the Map | List switch, and `view=map` in the address still opens it.
- Builder call: Cursor reads `*.md` agents directly in each of its six folders, not sub-folders (its docs do not say); the name is `name:` or the file name. The `.claude` and `.codex` folders follow "Include Third-Party Plugins" only if Cursor's docs say so.
- Builder call: Claude Code agents are named by `name:` only; a file without `name` or `description` is not listed; sub-folders are read.
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
- Builder call: Put back's note names the projects when only project rules offer the server; the held server's Details reads `/api/explain` to know which clients have the name.
- Builder call: a call time that cannot be read shows the count alone.
- Builder call: where a group still folds with "Show all N", "Show fewer" folds it back and sends focus to "Show all N" (Task 8 re-check).
- Builder call: a settings problem shows beside the servers and clients, never instead of them (Task 8 re-check).
- Builder call: only version commands are stopped on Ctrl+C; Codex's plugin list is not in this part.
- Builder call: an entry with both a command and an address, or with its token set twice, is refused rather than guessed.
- Builder call: the first-scan timing bound becomes 2.5 s; the check that no command ran stays.
- Builder call: the writing-tools checklist is a review opened from the held server's Details; the rules for folders Kitden no longer finds sit in the Kitden gateway block's Details, because they belong to the gateway and not to one server. Tools say On and Off in both.
- Builder call: in the demo, a gateway connect or switch says "Not part of the demo."; removing an entry that is not there fails, as a real client does.
- Builder call: a held-server Remove names the clients that lose the server in its done line, not in its title.
- Builder call: a preview that answers after the panel was closed is cancelled on the server and opens nothing.
