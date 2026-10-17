---
description: "Tasks for 001 agent setup inventory"
---

# Tasks: Agent setup inventory and safe controls

**Input**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md),
[contracts/](contracts/write-matrix.md), [research.md](research.md), [quickstart.md](quickstart.md)

**Tests**: included. The constitution (principle V) requires round-trip and fixture tests.

**Format**: `- [ ] ID [P] [Story] Action in file`. **[P]** = can run in parallel (different
files, no open dependency). **[US1]**…**[US5]** = user story from the spec.

## Phase 1: Setup

- [x] T001 Create `pyproject.toml` for uv: Python >=3.13, command `agentsetup` → `src/agentsetup/cli.py`, dependencies `mcp`, `starlette`, `uvicorn`, `tomlkit`, `watchfiles`; dev: `pytest`, `hypothesis`, `syrupy`
- [x] T002 Add ruff settings and the pytest marker `contract` in `pyproject.toml`
- [x] T003 [P] Add `.idea/`, `.venv/`, `__pycache__/` to `.gitignore`
- [x] T004 [P] Create `tests/fixtures/README.md`: one folder per client and version; real configs with every secret replaced by a sentinel string

## Phase 2: Foundation (blocks all stories)

- [x] T005 [P] Spike S1: find where Cursor stores plugin on/off; test that a write on a sandbox copy survives restart and team sync; write the result in `specs/001-agent-setup-inventory/spikes/s1-cursor-plugins.md`
- [x] T006 [P] Spike S4: check if the running Codex app overwrites outside edits to `config.toml`; write the result in `specs/001-agent-setup-inventory/spikes/s4-codex-app.md`
- [x] T007 [P] Spike S5: find where Cursor stores the "Third-Party Imports" switch; write the result in `specs/001-agent-setup-inventory/spikes/s5-cursor-imports.md`
- [x] T008 [P] List supported client versions and version commands (research R11) in `src/agentsetup/clients/versions.py`
- [x] T009 Create the types from [data-model.md](data-model.md) (Client, Source, Scope, Item, Project, Finding, Change, Gateway) with their enums in `src/agentsetup/model.py`
- [x] T010 [P] Write one redaction function: secret values become `[secret]`, `${VAR}` references stay, in `src/agentsetup/redact.py`
- [x] T011 [P] Test that no fixture sentinel survives redaction in `tests/security/test_redaction.py`
- [x] T012 Define the client adapter interface (detect, version, sources, items, allowed actions) in `src/agentsetup/clients/base.py`
- [x] T013 [P] Write the atomic file write: resolve real path, refuse hard-linked files, temp file in same folder, keep file mode, full fsync, `os.replace`, in `src/agentsetup/changes/atomic.py`
- [x] T014 [P] Test atomic write (mode kept, symlink target written, hard link refused) in `tests/unit/test_atomic.py`

**Checkpoint**: foundation ready.

## Phase 3: US1 — See every client's setup in one place (P1) 🎯 MVP

**Goal**: one page lists all MCP servers, skills, plugins, hooks and marketplaces of Claude Code, Codex and Cursor, with source, scope, on/off, and "unknown" plus reason.
**Test**: compare the page with each client's own settings; no client file changes.

- [x] T015 [P] [US1] Fixture tests for reading Claude Code and the Desktop Code tab (also: missing project folder, unreadable file, symlinked folder) in `tests/unit/test_read_claude_code.py`
- [x] T016 [P] [US1] Fixture tests for reading Codex (also: untrusted project, unknown format) in `tests/unit/test_read_codex.py`
- [x] T017 [P] [US1] Fixture tests for reading Cursor (also: locked state database, stale snapshot) in `tests/unit/test_read_cursor.py`
- [x] T018 [P] [US1] Claude Code adapter: MCP (local, project, user, managed, plugin, `claude_desktop_config.json`), settings, plugins, skills, hooks, marketplaces, projects; account items as unknown "stored_in_account", in `src/agentsetup/clients/claude_code.py`
- [x] T019 [P] [US1] Codex adapter: config layers (project layers only when trusted), MCP, plugins, marketplaces, skills, hooks, projects, in `src/agentsetup/clients/codex.py`
- [x] T020 [P] [US1] Cursor adapter: `mcp.json` files, skill and plugin folders, hooks; state database read-only with the key allowlist from research R5, in `src/agentsetup/clients/cursor.py`
- [x] T021 [US1] Build the inventory from all adapters, with unknown reasons, in `src/agentsetup/views/inventory.py`
- [x] T022 [US1] Add `agentsetup scan --json` (redacted, read-only) in `src/agentsetup/cli.py`
- [x] T023 [US1] Test that a scan changes no client file (hashes before and after) in `tests/unit/test_scan_read_only.py`
- [x] T024 [P] [US1] Security tests: wrong Host → 403, token → cookie, POST needs same Origin and `X-Tool-Request`, `/api/events` needs cookie and Origin, no CORS headers, item text with HTML shows as text, CSP blocks inline scripts, in `tests/security/test_web_security.py`
- [x] T025 [US1] Security layer from research R6 in `src/agentsetup/web/security.py`
- [x] T026 [US1] Read endpoints `/api/clients`, `/api/items`, `/api/projects` per [local-api.md](contracts/local-api.md) in `src/agentsetup/web/app.py`
- [x] T027 [US1] Start command: bind `127.0.0.1`, port 47800 or next free, print the token URL, open the browser, in `src/agentsetup/cli.py`
- [x] T028 [P] [US1] Debounced folder watcher that triggers a rescan and ignores the tool's own writes in `src/agentsetup/watch.py`
- [x] T029 [US1] Endpoints `/api/rescan` and `/api/events` in `src/agentsetup/web/app.py`
- [x] T030 [US1] Inventory page (clients with versions, items, source, scope, on/off, unknown reason); show all file text as plain text, no `innerHTML`, no inline scripts, no CDN, in `src/agentsetup/web/static/`

**Checkpoint**: MVP works on its own.

## Phase 4: US2 — What loads in a project, and what loads twice (P2)

**Goal**: per project, show what each client really loads, duplicates, cross-loading and overrides.
**Test**: fixture project with a skill in two folders Cursor reads and an MCP server in two scopes.

- [x] T031 [P] [US2] Tests for project views: Claude whole entry wins, Codex merges fields, Cursor project wins, in `tests/unit/test_effective.py`
- [x] T032 [P] [US2] Tests for findings: same item twice in one client = warning, in two clients = info, cross-loaded, scope override, in `tests/unit/test_findings.py`
- [x] T033 [US2] Project view builder in `src/agentsetup/views/effective.py`
- [x] T034 [US2] Findings builder, including `version_unsupported` (uses spike S5 for Cursor imports), in `src/agentsetup/views/findings.py`
- [x] T035 [US2] Endpoints `/api/projects/{id}/effective` and `/api/findings` in `src/agentsetup/web/app.py`
- [x] T036 [US2] Project view page in `src/agentsetup/web/static/`

## Phase 5: US3 — Bring MCP tools under the gateway (P3)

**Goal**: connect one gateway to all clients, flag MCP servers that bypass it, remove old direct entries; every change has preview, apply, verify and undo.
**Test**: quickstart scenario 3 in a sandbox home.

- [ ] T037 [P] [US3] Property tests for TOML and JSON edits: no-op keeps bytes, apply then undo restores bytes, only the target span changes, in `tests/property/test_edits.py`
- [ ] T038 [P] [US3] Format-preserving TOML edits with tomlkit in `src/agentsetup/changes/toml_edit.py`
- [ ] T039 [P] [US3] Minimal-span edits for strict JSON in `src/agentsetup/changes/json_splice.py`
- [ ] T040 [P] [US3] Runner for client commands (`claude mcp add-json/remove`, list `--json`) with redacted output in `src/agentsetup/changes/client_cli.py`
- [ ] T041 [P] [US3] Backups and redacted change log: folders 0700, files 0600, keep the larger of 30 days or 100 changes, in `src/agentsetup/changes/backup.py`
- [ ] T042 [US3] Change engine following the state diagram in [data-model.md](data-model.md): preview with masked diff, stale check, apply, verify, restore on failure, undo; default to user or local scope, warn on files usually in git, note when a restart is needed, refuse writes to files with an unrecognized format; in `src/agentsetup/changes/engine.py`
- [ ] T043 [P] [US3] Tests: changed file blocks apply, failed verify restores, undo blocked after outside edit, unknown format blocks writes, no item offers MCP add or on/off (FR-025), in `tests/unit/test_engine.py` and `tests/unit/test_actions.py`
- [ ] T044 [US3] Gateway registry (URL, interface link, auth type, key variable name only; file mode 0600) in `src/agentsetup/gateways.py`
- [ ] T045 [US3] Actions `gateway.connect` and `mcp.remove_direct` per [write-matrix.md](contracts/write-matrix.md) in `src/agentsetup/clients/claude_code.py`, `codex.py`, `cursor.py`
- [ ] T046 [US3] Mark MCP entries that go through a registered gateway, and add the finding `bypasses_gateway` (plugin, local or direct entry) for the rest, in `src/agentsetup/views/findings.py`
- [ ] T047 [US3] Endpoints for changes and gateways (`preview`, `apply`, `cancel`, `undo`, `/api/changes`, `/api/gateways`, `/api/commands`) in `src/agentsetup/web/app.py`
- [ ] T048 [US3] Gateway page: connect, bypass list, link to gateway interface, login commands, restart notes, in `src/agentsetup/web/static/`
- [ ] T049 [US3] Real-client test in a sandbox home: connect gateway, check client listings, remove a direct entry, undo both, bytes match the originals, in `tests/contract/test_gateway.py`

## Phase 6: US4 — Turn plugins on and off (P4)

**Goal**: plugin on/off for Claude Code and Codex; Cursor only after spike S1; show commands for install, update, move.
**Test**: disable a Claude Code plugin, restart, confirm, undo.

- [ ] T050 [P] [US4] Round-trip tests for plugin on/off in Claude Code and Codex in `tests/unit/test_plugins.py`
- [ ] T051 [US4] Claude Code plugin on/off with `claude plugin enable|disable --json`, verified by `claude plugin list --json`, in `src/agentsetup/clients/claude_code.py`
- [ ] T052 [US4] Codex plugin on/off through `plugins."<id>".enabled`, verified by `codex plugin list --json`; read every plugin's real on/off from that list; remote plugins are read-only (spike S4), in `src/agentsetup/clients/codex.py`
- [ ] T053 [US4] Cursor plugin control: unavailable, with the reason and where to change it in Cursor (spike S1), in `src/agentsetup/clients/cursor.py`
- [ ] T054 [US4] Show-only commands for install, update, move and marketplace add in `src/agentsetup/views/commands.py`
- [ ] T055 [US4] Plugin controls on the page in `src/agentsetup/web/static/`
- [ ] T056 [US4] Real-client plugin test in a sandbox home in `tests/contract/test_plugins.py`

## Phase 7: US5 — Ask the agent "show my setup" (P5)

**Goal**: a read-only MCP server gives agents the same answer as the page.
**Test**: quickstart scenario 5 with Codex.

- [ ] T057 [P] [US5] Tests: tools are read-only, output matches the page, no secrets, in `tests/unit/test_mcp_server.py`
- [ ] T058 [US5] MCP server with `show_setup`, `list_findings`, `explain_item`, `list_projects` (all read-only) per [mcp-tools.md](contracts/mcp-tools.md) in `src/agentsetup/mcp_server.py`
- [ ] T059 [US5] Command `agentsetup mcp` in `src/agentsetup/cli.py`
- [ ] T060 [US5] Action `setup_server.register` for each client, using the absolute install path, after confirmation, in `src/agentsetup/clients/claude_code.py`, `codex.py`, `cursor.py`
- [ ] T061 [US5] "Add to client" button on the page in `src/agentsetup/web/static/`
- [ ] T062 [US5] Real-client test with Codex in a sandbox home: register the setup server, handshake, call `show_setup`, undo restores bytes, in `tests/contract/test_mcp_handshake.py`

## Phase 8: Polish

- [ ] T063 [P] Secret and network sweep: no sentinel in page responses, change log, `scan --json` or MCP output, and no outgoing network calls, in `tests/security/test_no_secrets.py`
- [ ] T064 [P] Add usage to `README.md`: install, start, connect gateway, undo
- [ ] T065 Run quickstart scenarios 1–5 and the speed checks (first results under 10 s, rescan under 2 s); write results in `specs/001-agent-setup-inventory/validation.md`

## Order

- Phase 1 → Phase 2 → stories in order US1 → US2 → US3 → US4 → US5 → Phase 8.
- US1 is the MVP. US2 needs US1. US3 needs US1 and US2 (T046 extends `findings.py`). US4 and US5 need US3 (change engine).
- Spike results gate: S1 → T053, S4 → Codex writes in T045 and T052, S5 → T034.

## Parallel examples

- Phase 2: T005, T006, T007, T008, T010, T013 together.
- US1: T015–T020 together (tests and three adapters in different files).
- US3: T037–T041 together before T042.

## Strategy

1. Setup and foundation, including spikes.
2. US1, then stop and check it against the real clients (MVP).
3. Add one story at a time; each must pass its own test before the next.
