# Review follow-up: master plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every gap the two reviews and the cross-review found, in seven parts that each ship on their own.

**Architecture:** Each part is its own plan file (below) with its own tasks, tests and commits. This file fixes the order, the rules every part follows, and the names that cross part boundaries, so a part's implementer never has to guess what a neighbor called something.

**Tech Stack:** Python 3.13, Starlette, the official MCP SDK 2.3, tomlkit, watchfiles; plain ES modules and one CSS file; pytest with hypothesis and syrupy; node's test runner for the page's pure functions.

**Spec:** `docs/superpowers/specs/2026-10-21-review-follow-up-design.md`

## Order

| Part | Plan file | Ships |
| --- | --- | --- |
| 1 Truth on the page | `2026-10-21-follow-up-part1-truth.md` | Overview knows the Kitden gateway; scope before the click; no useless notes; words match the code; the gateway says what it governs; short Gateway page |
| 2 The gateway's access contract | `2026-10-21-follow-up-part2-gateway-contract.md` | strict mode; new tools wait; refusal at call time; unknown folder said plainly; reads/writes helper and the batch switch; call counts |
| 3 Complete management | `2026-10-21-follow-up-part3-management.md` | remove a plugin, a skill, a gateway server; put a held server back; add a server to another client; align a project; add into one project |
| 4 Fast to open, and measured | `2026-10-21-follow-up-part4-speed.md` | versions in the background with a disk cache; the measurement script and its two numbers |
| 5 Secrets have a lifecycle | `2026-10-21-follow-up-part5-secrets.md` | Keychain for gateway secrets; backups say when they hold one; OAuth spike, then logins in one place |
| 6 The whole picture | `2026-10-21-follow-up-part6-instructions.md` | the Instructions tab; tool counts |
| 7 Linux and Windows | `2026-10-21-follow-up-part7-platforms.md` | Linux first, then Windows |

Run the parts in this order. Part 5 waits for Part 4 (the owner's decision). Inside a part,
tasks run in their numbered order. Part 8 of the spec (docs, roadmap, releases, checks) is the
last task of every part, not a part of its own.

## Rules every part follows

- `AGENTS.md`: code, comments, UI text and docs in simple English, short and plain. Every change
  of a client's settings goes through preview → Apply with a backup → verify → Undo, through the
  change engine (`src/kitden/changes/engine.py`) and never any other way. Main pages show a
  name, the client and an action; paths, addresses and commands stay in Details.
- `docs/design.md` for how the page looks and moves: new text is tested in
  `tests/unit/test_page_words.py`; helper logic in the page is a pure function exported from a
  module under `src/kitden/web/static/js/` and tested with `node --test tests/frontend/*.test.mjs`.
- Tests use sandbox homes only: `make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2",
  "cursor/3.21.16")` and `write_cursor_fixture_state(home)` from `tests/conftest.py`; the
  `no_version` fixture stubs the version commands; every secret in a fixture is a
  `SENTINEL_SECRET_*` string and `tests/security/test_no_secrets.py` fails if one shows anywhere.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`,
  `node --test tests/frontend/*.test.mjs`. All three pass or the commit waits.
- Commit messages: a short plain subject, one to three simple lines, no prefix such as `feat:`.
  Example: `Gateway: strict mode per server`.
- A fact about another tool (a client's file format, a CLI flag, an MCP rule) is checked against
  that tool's current docs before it is relied on, and the check date goes next to the claim in
  a comment, as the code does today (`checked 2026-10-21`).
- No new runtime dependency unless the part's plan says so and why.
- Each part's last task updates `README.md` (the section it touches), `ROADMAP.md` (move the
  shipped part from "## Planned" to "### Not released yet" under Done) and, where the part adds
  a real-client check, `docs/development.md`. Release notes are written
  at release time (`docs/development.md`, Release), not per part.

## Names that cross part boundaries

A part that defines a name below must use it exactly; a part that uses one must not rename it.

| Name | Defined in | Used in | What it is |
| --- | --- | --- | --- |
| `rules.global[<server>].mode == "strict"` | Part 2 | Parts 3, 5 | the strict flag in `gateway.json`, global only |
| `GATEWAY_STRICT = "gateway.strict"` | Part 2 (`src/kitden/changes/actions.py`) | — | the action of the strict switch; params `{"server": str, "state": "on" | "off"}` |
| `GATEWAY_RULES = "gateway.rules"` | Part 2 | Part 3 (align review reuses the pattern) | one review with several rule steps; params `{"server": str, "tools": list[str], "state": "on" | "off", "project": str | None}` |
| `hint` and `hint_from` on a tool in `tools_view` | Part 2 (`src/kitden/local_gateway/views.py`) | — | `hint` is `"reads"`, `"writes"`, `"may write"` or `"unknown"`; `hint_from` is `"server"`, `"name"` or `None` |
| `is_allowed(home, chain, server, tool) -> bool` | Part 2 (`src/kitden/local_gateway/settings.py`) | Part 5 (the refresh path checks the server is on) | reads `gateway.json` again and answers for one tool |
| `count_call(home, server, tool) -> None` | Part 2 (`src/kitden/local_gateway/settings.py`) | — | adds one to `gateway-calls.json` |
| `translate_entry(entry: dict, client: str) -> dict` | Part 3 (`src/kitden/changes/server_entry.py`, new) | Part 3 (3.3 put back, 3.4 add, 3.5 align) | a held or direct entry in the target client's format; raises `ValueError` with the reason when a `${VAR}` reference cannot be kept |
| `ClientAdapter.add_server_step(name: str, entry: dict) -> Step` | Part 3 (`src/kitden/clients/base.py` and the three adapters) | Part 3 | a user-scope MCP entry in that client, built on each adapter's `_add_entry` |
| `FolderRemoval` and `REMOVE_FOLDER = "remove_folder"` | Part 3 (`src/kitden/model.py`) | — | a step that backs up and removes a skill folder; Undo copies it back |
| `{"keychain": "<server>/<key>"}` | Part 5 (`src/kitden/local_gateway/keychain.py`, new) | Part 3 (put back resolves it when present), Part 7 (the OS twin keeps the shape) | a reference in `gateway.json` in place of a secret value |
| `keychain.store(server, key, value) -> dict`, `keychain.read(ref: dict) -> str | None`, `keychain.delete(ref: dict) -> None` | Part 5 | Part 3, Part 7 | the three calls; `store` returns the reference dict |
| `resolve_entry(entry: dict) -> dict` | Part 5 (`src/kitden/local_gateway/keychain.py`) | Part 3 (put back), the proxy | the entry with every reference replaced by its value; a plain entry comes back as it is. Until Part 5 exists, Part 3 treats every entry as plain |
| `cached_version(home, client) -> str | None` and `refresh_versions(home, clients) -> dict[str, str | None]` | Part 4 (`src/kitden/clients/version_cache.py`, new) | Part 7 (the data folder moves) | the disk cache of version commands |
| `ItemKind.INSTRUCTIONS = "instructions"` | Part 6 (`src/kitden/model.py`) | — | the new read-only kind; its `summary` carries `("category", "instructions" | "command" | "agent")` |
| `kitden.paths` (new module) | Part 7 | — | every OS-specific path in one place; `data_dir` in `src/kitden/gateways.py` delegates to it |

## Review focus, whole project

Each part's plan has its own Review Focus. These five cross the parts and each one's test
is named in the part that owns the code:

1. A `gateway.json` written by an older Kitden (no `mode`, no `keychain` references) must read
   exactly as before: Part 2 and Part 5 both keep a test that loads the fixture settings of
   today and get the same `allowed_tools` answer.
2. A secret must never reach the page, a review, a record's masked diff, an error message or a
   log: every part that touches an entry runs its new output through `redact` and adds a
   sentinel to a fixture so `tests/security/test_no_secrets.py` would catch it.
3. A change that is applied and then undone leaves the client's file byte-for-byte as it was,
   also when the client rewrote the file in between (`check="entry"`): Part 3's new steps use
   the engine's existing paths and test Undo after an outside edit.
4. Nothing on the first scan waits for a command: Part 4's test runs `build_inventory` with a
   version command that sleeps and asserts the scan returns before it.
5. The gateway must still start when the data folder is unreadable or a file in it is broken:
   Part 2 and Part 5 keep the "reads as empty, says so" behavior for every new file.
