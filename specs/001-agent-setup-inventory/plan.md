# Implementation Plan: Agent setup inventory and safe controls

**Branch**: `001-agent-setup-inventory` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-agent-setup-inventory/spec.md`

## Summary

A local tool for one developer on macOS. It reads the setup of Claude Code (including the Claude
Desktop Code tab), Codex and Cursor; shows every MCP server, skill, plugin, hook and marketplace
with its source and scope; builds a per-project view of what each client really loads; and flags
duplicates and cross-loading. MCP tools are managed in an existing gateway (Obot or MetaMCP; owner
decision "gateway first", [research R13](research.md#r13-gateway-first-for-mcp-tools)): the tool
connects the gateway to every client once, flags MCP servers that bypass it, and can remove old
direct entries. Plugins are turned on and off from the page. Every change happens only after an
explicit Apply, through each client's own command or a format-preserving edit, with backup,
verification and undo. A read-only MCP server gives agents the same answer.

Technical approach (from [research.md](research.md)): an own tool (not a Cross-Code Organizer
contribution), one Python 3.14 package distributed with `uv`, a Starlette page bound to
`127.0.0.1` with a per-start token, client adapters behind one interface, a change engine with
atomic writes and hash-based stale checks, and a stdio MCP server built with the official SDK.
Spikes S1, S4 and S5 are done: Cursor plugins stay read-only (no on/off to write), and Codex
writes are safe while the app runs (S2 and S3 are no longer needed after gateway first).

## Technical Context

**Language/Version**: Python 3.14 (minimum 3.13), managed with uv 0.13

**Primary Dependencies**: `mcp` 2.3 (stdio server), `starlette` 1.8 + `uvicorn` 0.54 (local page),
`tomlkit` 0.15 (format-preserving TOML), `watchfiles` 1.3 (FSEvents); stdlib `json`, `tomllib`,
`sqlite3` (read-only Cursor state), `hashlib`, `secrets`

**Storage**: files only, under `~/Library/Application Support/<tool>/`: change log (redacted),
backups (mode 0600), registered gateways; no database

**Testing**: `pytest` 9, `hypothesis` (round-trip properties), `syrupy` (snapshots); fixture
configs per client version with secret sentinels; local contract tests against real clients in
sandbox homes

**Target Platform**: macOS (Apple silicon and Intel), tested on the owner's macOS 26

**Project Type**: single Python package providing a CLI, a local web page and a stdio MCP server

**Performance Goals**: first results within 10 s of start (SC-006); project view usable within
30 s of opening the page (SC-001); rescan after a file change within 2 s for the owner's setup

**Constraints**: loopback only; no outgoing network calls (FR-038); no writes without Apply
(FR-015); secret values never leave the server process; works with clients that rewrite their own
files; unknown formats block writes

**Scale/Scope**: 3 clients, about 4 client surfaces; hundreds of items; tens of projects
(the owner has about 9 Claude Code and 19 Codex projects)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Before research | After design |
| --- | --- | --- | --- |
| I. Clear communication | Docs in simple English with diagrams and tables; discussion in Russian | Pass | Pass: plan, research, data model and contracts use tables and diagrams |
| II. Specify before building | Approved spec; dated, sourced research; existing tools checked before novelty claims | Pass: spec approved via brief; CCO and others reviewed | Pass: research.md has dated sources; R1 records the CCO decision |
| III. Safe changes to client setups | Writes only after explicit action; client CLI preferred; no undocumented storage writes without a recorded spike; backup, verify, undo; preserve unknown settings | Pass by design intent | Pass with one justified deviation: Codex uses our format-preserving edit instead of `codex mcp add` (see Complexity Tracking). Undocumented storage (Cursor state database) stays read-only (spike S1). Gateway first reduces MCP writes to the gateway entry and removals |
| IV. Honest and private inventory | Provenance for every item; "unknown" with a reason; secrets never shown or copied; no data leaves the machine | Pass | Pass: Source and Item models carry provenance and `unknown_reason`; redacted model shared by page, `scan --json` and MCP; Cursor database read through a key allowlist; file text shown only as plain text, CSP without inline scripts (FR-041) |
| V. Verify against real clients | Pinned versions; fixtures; round-trip tests; fail safely on format changes | Pass | Pass: R10 and R11 define fixtures, property tests, sandbox contract tests and version ranges; unknown formats block writes (FR-042); every write path has a round-trip test |
| VI. Keep it local and simple | No server, account or login; reuse existing tools; file-access component separate from UI | Pass | Pass: one package; the change engine and adapters sit behind the local API contract; gateways are reused, not built |

No unjustified violations. Gates pass.

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-setup-inventory/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── cli.md           # Commands and exit codes
│   ├── local-api.md     # Page ↔ local component API and security rules
│   ├── mcp-tools.md     # Read-only MCP tools
│   └── write-matrix.md  # Which actions write, how, and which wait for spikes
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── spikes/              # Spike results S1, S4, S5 (created during implementation)
└── tasks.md             # Phase 2 output ($speckit-tasks; not created here)
```

### Source Code (repository root)

```text
pyproject.toml                 # Package metadata, entry point "<tool>", uv-managed
src/agentsetup/                # Working package name; product name still open
├── cli.py                     # start page, scan, mcp, --version
├── model.py                   # Client, Source, Item, Project, Finding, Change, Gateway
├── redact.py                  # Single redaction path for page, scan and MCP output
├── gateways.py                # Registered gateways (URL, interface link, key variable name)
├── clients/
│   ├── base.py                # Adapter interface: detect, version, sources, items, actions
│   ├── versions.py            # Supported versions and version commands
│   ├── claude_code.py         # CLI and Desktop Code tab
│   ├── codex.py
│   └── cursor.py              # Files plus read-only state-database allowlist
├── views/
│   ├── inventory.py           # All items from all adapters, with unknown reasons
│   ├── effective.py           # Per-project effective view by client rules
│   ├── findings.py            # Duplicates, cross-loading, overrides, bypass, unknown state
│   └── commands.py            # Client commands shown for actions the tool does not do
├── changes/
│   ├── engine.py              # preview, stale check, apply, verify, undo, state machine
│   ├── backup.py              # Backup layout, retention, change log
│   ├── atomic.py              # Temp file, F_FULLFSYNC, os.replace, hard-link refusal
│   ├── toml_edit.py           # Format-preserving TOML edits (tomlkit)
│   ├── json_splice.py         # Minimal span edits for strict JSON
│   └── client_cli.py          # Calls to claude/codex CLIs with redacted capture
├── web/
│   ├── app.py                 # Starlette routes per contracts/local-api.md
│   ├── security.py            # Token, cookie, Host, Origin, Sec-Fetch-Site checks
│   └── static/                # Plain HTML, CSS, JS; no CDN
├── mcp_server.py              # Read-only tools per contracts/mcp-tools.md
└── watch.py                   # Debounced directory watching

tests/
├── fixtures/                  # Per client and version; secrets replaced by sentinels
├── unit/
├── property/                  # Round-trip and span-preservation properties
├── security/                  # Token, Host, Origin, CSRF, secret sentinel checks
└── contract/                  # Real clients in sandbox homes (local only, marker "contract")
```

**Structure Decision**: one Python package (`src/agentsetup`), because the page, the CLI and the
MCP server share the same model, adapters and redaction. The "local component" from the
constitution is `clients/`, `views/` and `changes/`; `web/` and `mcp_server.py` only call it.
This keeps a later team server possible without a rewrite.

## Delivery order

Same order as [tasks.md](tasks.md).

| Order | Work | Spec link |
| --- | --- | --- |
| 1 | Foundation: spikes S1, S4, S5; versions; model; redaction; atomic write | FR-006, FR-009, FR-028 |
| 2 | US1: adapters, inventory, `scan --json`, secure read-only page, watcher | FR-001–FR-009, FR-036–FR-038, FR-041, FR-042 |
| 3 | US2: project views and findings | FR-010–FR-014 |
| 4 | US3: change engine, gateway connection, bypass findings, direct-entry removal | FR-015–FR-026, FR-033–FR-035, FR-039, FR-040 |
| 5 | US4: plugin on/off and shown commands | FR-027–FR-029 |
| 6 | US5: read-only MCP server and its registration | FR-030–FR-032 |

## Risks

| Risk | Mitigation |
| --- | --- |
| Clients change file formats often | Version pinning, fixtures per version, unknown formats block writes |
| Claude Code rewrites `~/.claude.json` while running | Use `claude mcp` commands for that file; stale checks; verify after write |
| Codex desktop app may overwrite outside edits | Spike S4 passed: edits survive; keep stale checks by hash; restart notice |
| Cursor state is undocumented | Read-only through an allowlist; spike S1 found no plugin on/off, so Cursor plugins stay read-only |
| The product depends on a gateway for MCP control | Work with any MCP gateway URL (Obot or MetaMCP); without a gateway the page still shows everything and flags all MCP servers as bypassing |
| Plugin MCP and local MCP servers cannot go through a remote gateway | Flag them with their source so the owner knows what is outside gateway control |
| Installed Claude Code 2.1.283 may exit before a plugin write finishes | Always verify with `claude plugin list --json`; recommend 2.1.302 or later |
| JSON-with-comments editing is weak in Python | Only strict JSON files are edited; span splicer covered by property tests |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Codex writes (gateway entry, setup server entry, direct-entry removal, plugin on/off) use our format-preserving TOML edit instead of the client's CLI (constitution III prefers client CLIs) | `codex mcp add` and `remove` rewrite `[mcp_servers]` and drop comments; constitution III also requires preserving settings the tool does not understand | Using `codex mcp add` would silently delete the owner's comments; Codex has no CLI for plugin on/off at all |
