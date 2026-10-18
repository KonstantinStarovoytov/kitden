# Tasks: Kitden name and one-command page

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. Constitution V asks for round-trip tests on every write path; write each
test first and watch it fail.

Format: `[ID] [P?] [Story] Description`. `[P]` = can run in parallel (different files).

## Phase 1: US1 — Kitden everywhere (P1) 🎯 MVP

**Goal**: one name for the package, command, page and MCP server.
**Independent test**: `kitden --version`, page title, MCP entry name in a sandbox client.

- [X] T001 [US1] Move `src/agentsetup` to `src/kitden` with `git mv`; update imports, `pyproject.toml`
  (name `kitden`, script `kitden`, version 0.2.0) and `uv.lock`. The whole suite stays green.
- [X] T002 [US1] Tests first in `tests/unit/test_cli.py`, `tests/unit/test_mcp_server.py`,
  `tests/unit/test_setup_server.py`: `--version` prints `kitden 0.2.0`; MCP server name `kitden`;
  the setup server entry is named `kitden` and runs `.../kitden mcp`. Then change `cli.py`,
  `mcp_server.py` (name, instructions say `kitden open`) and `SETUP_NAME` in `clients/base.py`.
- [X] T003 [P] [US1] Page: brand and titles say Kitden; theme key `kitden-theme` (read the old key
  once); `SETUP_NAME` in `web/static/js/agents.js`. Update `tests/security/test_static_files.py`.

**Checkpoint**: a fresh install works end to end under the new name.

## Phase 2: Foundation for US2 — several steps on one file

- [X] T004 [US2] Tests first in `tests/unit/test_engine.py` and `tests/property/test_edits.py`: two
  steps on one JSON file and one TOML file apply in order, verify, and Undo to the exact bytes;
  entry-level Undo still works after an outside edit elsewhere in the file; a failing second step
  restores the original bytes; two steps on the same key are refused. Then change
  `changes/engine.py` ([R2](research.md#r2-several-steps-on-one-file-in-one-change)).

## Phase 3: US2 — Nothing is lost (P1)

**Goal**: gateways, history and Undo survive; old MCP entries update in one reviewed change.
**Independent test**: sandbox home with the old data folder and old entries (quickstart §2–3).

- [X] T005 [P] [US2] Tests first in `tests/unit/test_data_folder.py`: only old folder → copied with
  modes, backup paths rewritten, old folder unchanged; both → new used and one line printed; copy
  fails → no partial folder, old intact; Undo of an old change works after the old folder is
  deleted. Then `ensure_data_folder()` in `gateways.py`, called by every CLI command
  ([R7](research.md#r7-data-folder-copy)).
- [X] T006 [P] [US2] Tests first in `tests/unit/test_setup_update.py`: state per client (`added`,
  `old`, `missing`, `not_installed`); an `agentsetup` entry running another program is ignored;
  `command_exists` is false when the old command is gone; a project-level `agentsetup` entry
  is ignored. Then `views/setup_server.py` and
  `GET /api/setup-server` in `web/app.py` (test in `tests/unit/test_api_views.py`).
- [X] T007 [US2] Tests first: `setup_server.update` builds remove + add per client; only remove when
  `kitden` already exists; 422 for a target that is not an old entry and when `kitden` is not
  installed. Then `changes/actions.py` and the preview branch in `web/app.py`. Depends on T004, T006.
- [ ] T008 [US2] Contract test in `tests/contract/test_mcp_handshake.py`: real `claude` and `codex`
  in a sandbox home with an old entry → update → `claude mcp get kitden` and `codex mcp list --json`
  show `kitden`; Undo restores the files byte for byte.
- [ ] T009 [US2] Page: Agents shows "Old entry" with "Update to Kitden…" (and "old command is
  missing" when so); Overview shows an attention card for old entries that opens Agents. Files:
  `web/static/js/agents.js`, `views/overview.py`, `tests/unit/test_overview.py`. Browser check.

**Checkpoint**: quickstart §2 and §3 pass on a sandbox home.

## Phase 4: US3 — Open the page with one command (P2)

**Goal**: `kitden open` returns at once; one page per home folder.
**Independent test**: quickstart §4.

- [ ] T010 [US3] Tests first in `tests/unit/test_page.py`: the page lock lets only one page run per
  home; `page.json` has mode 0600 and is removed on stop; a record without a held lock is stale.
  Then `page.py` ([R3](research.md#r3-one-page-per-home-folder), [R4](research.md#r4-page-record)).
- [ ] T011 [US3] Tests first: `open` with a running page opens it and starts nothing; with no page it
  starts `serve --background`, waits for the record and opens it; exit 4 when the page does not
  start in 5 s; `--no-browser` only prints the link; `kitden` with no command equals `open`. Fake
  the starter and the browser. Then `cli.py` and `page.py` ([R5](research.md#r5-starting-in-the-background)).
- [ ] T012 [P] [US3] Tests first in `tests/security/test_web_security.py`: the cookie is named
  `kitden_session_<port>`; a session for one port is refused by a page on another port. Then
  `web/security.py`.

## Phase 5: US4 — Stop when no tab is open (P3)

**Goal**: background pages stop after 10 minutes without a tab, never during a change.
**Independent test**: quickstart §5 (tests pass a short wait).

- [ ] T013 [US4] Tests first in `tests/unit/test_page.py`: no event stream for the wait → stop;
  a tab within the wait → keeps running; a running change delays the stop; a page that never had a
  tab stops; `serve` in the foreground never stops by itself. Then idle tracking in `web/app.py`
  and the stop timer in `page.py` ([R6](research.md#r6-stopping-when-no-tab-is-open)).

## Phase 6: Polish

- [ ] T014 [P] Docs: README (install, `kitden open`, update old entries, `uv tool uninstall
  agentsetup`), constitution 2.1.1 (name decided, title), `AGENTS.md` title, brief and naming
  research links. Feature 001 documents stay as history.
- [ ] T015 Full checks: `uv run pytest -q`, contract tests, ruff; quickstart §1–5 on a sandbox home;
  browser check of Agents and Overview; `rg -i agentsetup src` shows only migration code (SC-006).
- [ ] T016 Owner's real setup (quickstart §6): the owner stops the old page, installs Kitden, updates
  the Codex entry from Agents, and removes the old tool.

## Order

T001 → T002 → T003 → T004 → (T005, T006) → T007 → T008 → T009 → T010 → T011 → T012 → T013 →
T014 → T015 → T016. T005, T006, T012 and T014 touch separate files.

## Strategy

Ship in two groups: US1 + US2 (the rename is only safe with the data and entry move), then
US3 + US4. Commit after each task with a short plain message.
