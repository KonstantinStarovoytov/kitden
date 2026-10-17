# Validation: feature 001

Date: 2026-10-17. macOS (Darwin 25.6), Python 3.14.3 with uv. Clients: Claude Code 2.1.283
(Desktop Code tab 2.1.299), Codex CLI 0.159.2 (Codex app 26.928.40906), Cursor 3.25.6.

Writes were first tested in sandbox homes. The owner then ran scenarios 3 and 5 on the real
clients, pressing Apply on the page (see "Real clients" below).

## Automated checks

| Check | Result |
| --- | --- |
| `uv run pytest` (unit, property, security, including the secret and network sweep) | 244 passed |
| `uv run pytest -m contract` (real `claude` and `codex` commands, sandbox homes) | 5 passed |
| `ruff check`, `ruff format --check` | Clean |

## Quickstart scenarios

| Scenario | Where | Result |
| --- | --- | --- |
| 1. Inventory in one place | Owner's computer, read-only | Pass. 4 clients found with versions; 188 items, 28 projects. Claude account plugins show as "unknown: stored in account". Page listens on `127.0.0.1` only. 5 client config files have the same hashes after start, scan and stop |
| 1.5 No secret values | Owner's computer, read-only | Pass after a fix (see below). `scan --json` has no token-shaped strings; 4 items show "secret hidden" |
| 2. Project view, duplicates, cross-loading | Fixtures; owner's data (US2) | Pass. Override, merge and cross-loading tests; real data showed Cursor loading `superpowers` twice |
| 3. Gateway connect, bypass list, remove, undo | Sandbox page in the browser; contract test; owner's clients | Pass. Entries confirmed by `claude mcp get` and `codex mcp list --json`; keys written as `${GW_KEY}`, `bearer_token_env_var`, `${env:GW_KEY}`; undo restored all files byte for byte; a hand edit after preview stopped Apply. Live gateway: see "Real clients" |
| 4. Plugins | Sandbox page; contract test | Pass. `claude plugin list --json` showed the plugin off, undo restored bytes; Cursor shows where to change plugins; "Install in Codex" shows commands and runs nothing |
| 5. Agent tool | Sandbox page; contract test; owner's Codex | Pass after a fix. Registration, stdio handshake and `show_setup` pass; a real Codex session matched the page; see "Real clients" |

## Speed (owner's computer)

| Measure | Goal | Result |
| --- | --- | --- |
| Start command to first results (SC-006) | Under 10 s | 4.2 s |
| Rescan | Under 2 s | 0.02 s (client commands are cached) |

## Success criteria

| Criterion | Status |
| --- | --- |
| SC-001 project view within 30 s | Pass |
| SC-002 nothing silently missing | Pass for the US1 audit and the Cursor recheck after spike S1; a full manual audit is still open |
| SC-003 undo restores exactly | Pass in every property and contract round trip |
| SC-004 zero secret values | Pass after the fix below |
| SC-005 gateway connect under 2 minutes | Pass in the sandbox (add gateway, preview, apply took well under a minute) |
| SC-006 first results under 10 s | Pass (4.2 s) |
| SC-007 agent answer equals the page | Pass: tests compare item by item; a real Codex session returned the same 63 items as the page |
| SC-008 two weeks of daily use | Open (owner) |
| SC-009 every bypassing MCP server listed | Pass on fixtures and the sandbox; real audit after connecting a gateway is open |

## Real clients (owner's computer)

Gateway: MetaMCP 2.4.22 on `http://localhost:12008/metamcp/local/mcp`, auth off, one tool
(`agent-docs__search_docs`) through the agent-docs bridge.

| Step | Result |
| --- | --- |
| Register the gateway on the page | Codex's existing `metamcp-local` entry was recognized and left the "going around the gateway" list |
| Connect Claude Code and Cursor (entry `metamcp`) | Applied and checked. `claude mcp get metamcp`: Connected. Cursor after restart: connected, tool listed (Cursor's own per-tool switch was off) |
| Add "show my setup" to Codex | Applied and checked; Codex started `agentsetup mcp` from the repository's `.venv` |
| Ask Codex for `show_setup` | Same as the page: 7 MCP servers, 21 plugins, 33 skills, 2 marketplaces; `metamcp-local` marked via gateway |
| Ask Codex to turn off a plugin through the tool | First try: the tool refused, but the agent edited `config.toml` itself. After the fix below: the agent refused and pointed to the page |
| Turn the plugin back on from the page | Applied and checked; in the change log |

These real changes stay in place and can be undone from the change log: `metamcp` in Claude Code
and Cursor, and `agentsetup` in Codex.

## Found and fixed during validation

- **Secret in MCP arguments.** A Cursor entry passed a key as `docker run -e N8N_API_KEY=<token>`.
  Redaction only knew `--flag=value` and whole-string tokens, so the token reached the item
  summary (page, `scan --json`, MCP). Now `NAME=value` arguments with a secret-like name and tokens
  inside longer strings are hidden. Tests and a fixture case were added.
- **Agent worked around the read-only tool.** Asked to turn off a plugin, Codex edited
  `config.toml` directly. Tool descriptions now say not to edit client settings files and to send
  the developer to the page; the retry was refused.
- **Page did not stop with an open browser tab.** The event stream kept the server waiting; the
  stop now waits at most 2 seconds.

## Open items

- Decided (owner, 2026-10-17): keep running `codex plugin list --json` in the scan. It shows remote
  Codex plugins' on/off, and Codex then asks chatgpt.com for the owner's installed plugins. The
  tool's own process makes no network connections (sweep test); the README says this.
- A tool call through the gateway from inside an agent session (the connection and tool list
  were checked).
- The page scrolls sideways on narrow windows (part of the separate design task).
