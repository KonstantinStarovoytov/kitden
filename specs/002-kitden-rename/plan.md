# Implementation Plan: Kitden name and one-command page

**Branch**: `002-kitden-rename` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-kitden-rename/spec.md`

## Summary

Rename the product from the working name `agentsetup` to Kitden: package, command, page, MCP
server name and data folder. Copy the old data folder once, so gateways, history and Undo
survive. Detect MCP entries made by the working version and offer "Update to Kitden" as one
reviewed change. Add `kitden open`: it opens the running page or starts one in the background.
Allow one page per home folder, and stop a background page after 10 minutes without a tab.

## Technical Context

**Language/Version**: Python 3.13+ (as feature 001), browser JavaScript modules for the page

**Primary Dependencies**: existing only — Starlette, uvicorn, MCP SDK 2.x, tomlkit; no new ones

**Storage**: files in `~/Library/Application Support/kitden` (gateways, change history, backups,
page record)

**Testing**: pytest (unit, property, security, contract with real `claude` and `codex` in sandbox
homes); browser check on a sandbox home

**Target Platform**: macOS, local user account

**Project Type**: local CLI with a local web page and a stdio MCP server

**Performance Goals**: `kitden open` returns in under 5 s (cold) and under 2 s (page running)

**Constraints**: no new dependencies; no writes to client settings without Apply; the page
record is private to the user; secrets never logged

**Scale/Scope**: one developer, one page per home folder

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
| --- | --- | --- |
| I. Clear communication | Spec, plan and UI text in simple English; owner talk in Russian | Pass |
| II. Specify before building | Spec, clarifications, research decisions recorded here | Pass |
| III. Safe changes | "Update to Kitden" goes through preview, backup, check and Undo; nothing is updated automatically; Claude Code uses its own CLI | Pass |
| IV. Honest and private | Old entries are shown with their client and file; the page record (with the start link) is readable only by the user; no secret in logs | Pass |
| V. Verify against real clients | Round-trip tests for the two-step update in each client; contract test with real `claude` and `codex`; owner's real Codex entry checked last | Pass |
| VI. Local and simple | No new dependency; the background page is started only on request and stops by itself | Pass, see note |

Note on VI: a background process is new. It is justified by the owner's request (open from an
agent without blocking it) and bounded by the 10-minute stop.

The constitution says the product name is still open; this feature amends it (patch 2.1.1).

Re-check after Phase 1: no change. The engine change (several steps in one file) keeps every
safety rule: one backup per file, restore on failure, exact Undo ([research R2](research.md#r2-several-steps-on-one-file-in-one-change)).

## Project Structure

### Documentation (this feature)

```text
specs/002-kitden-rename/
├── plan.md          # This file
├── research.md      # Decisions R1–R8
├── data-model.md    # Page record, old entry, data folder copy
├── quickstart.md    # How to check the feature
├── contracts/       # CLI, local API and MCP changes
└── tasks.md         # Made by speckit-tasks
```

### Source Code (repository root)

```text
src/kitden/                  # renamed from src/agentsetup (git mv)
├── cli.py                   # open (default), serve, scan, mcp, --version
├── page.py                  # new: page record, lock, background start, idle stop
├── gateways.py              # data folder name + one-time copy of the old folder
├── changes/engine.py        # several steps on one file, applied in order
├── changes/actions.py       # setup_server.update action
├── views/setup_server.py    # new: setup server state per client (added, old, missing)
├── web/app.py               # /api/setup-server, idle tracking, cookie per port
├── web/security.py          # cookie name per port
└── web/static/js/agents.js  # "Update to Kitden" and old-entry notes

tests/
├── unit/test_page.py            # new
├── unit/test_data_folder.py     # new
├── unit/test_setup_update.py    # new
├── property/test_edits.py       # two steps on one file
└── contract/test_mcp_handshake.py  # real claude and codex: update old entry, undo
```

**Structure Decision**: Keep the single-package layout from feature 001 and rename the package
folder. New logic goes into two small modules (`page.py`, `views/setup_server.py`).

## Complexity Tracking

No constitution violations to justify.
