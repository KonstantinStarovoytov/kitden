# Quickstart: validating agent setup inventory

**Feature**: [spec.md](spec.md) | **Date**: 2026-10-17

This guide proves the feature works end to end. It is a validation guide, not an implementation
guide. `<tool>` is a placeholder until the product name is chosen.

## Prerequisites

- macOS with `uv` installed (`brew install uv`); `uv` provides Python 3.14.
- Claude Code, Codex (CLI or ChatGPT desktop app) and Cursor installed, versions per
  [research R11](research.md#r11-supported-client-versions-first-release).
- For write scenarios: a **sandbox home** so real settings are never touched:
  copy the fixtures in `tests/fixtures/sandbox-home/` to a temporary folder and start the tool with
  `HOME=<sandbox>` and `CODEX_HOME=<sandbox>/.codex`. Real-machine checks are read-only.

## Scenario 1 — Inventory in one place (User Story 1, SC-002, SC-006)

1. Run `uvx <tool>` (or `<tool>` after `uv tool install`).
2. Expect the browser to open within 10 seconds with all three clients listed, each with a version.
3. Pick five items you know from each client's own settings. Expect each to appear with the correct
   source file and scope.
4. Expect Claude chat or Cowork plugins to appear only as "unknown: stored in the account".
5. Search the page for any known secret value from your configs. Expect zero matches; entries with
   secrets show "secret present".
6. Stop the tool. Expect no client config file changed (compare hashes before and after).
7. From another computer on the same network, try the page's port. Expect no connection.

## Scenario 2 — Project view, duplicates and cross-loading (User Story 2, SC-001)

Uses the sandbox fixture `cross-loading/`: one skill in `~/.claude/skills` and `~/.agents/skills`,
one MCP server defined both user-wide and in `.cursor/mcp.json`.

1. Open the fixture project in the page.
2. Expect within 30 seconds: Cursor's view shows the skill as cross-loaded with both folders;
   the MCP server shows a scope override with the project entry winning.
3. Expect the same skill set up in Claude Code and Cursor to be marked "information", not a warning.

## Scenario 3 — Bring MCP under the gateway (User Story 3, SC-003, SC-005, SC-009)

1. Start a local MCP gateway (for example the MetaMCP setup from the
   [gateway trial](../../docs/research/gateway-trial-2026-10-16.md)).
2. In the sandbox home, register its URL with a key stored as an environment variable name.
   Preview "connect to all clients". Expect a masked diff per client, a "restart needed" note, and
   no file change before Apply.
3. Apply. Expect each client's config to contain the gateway entry (`codex mcp list --json` with the
   sandbox `CODEX_HOME` shows it), the key written as a reference (`${VAR}`, `bearer_token_env_var`,
   `${env:NAME}`), and comments elsewhere in `config.toml` unchanged.
4. Expect every other MCP server in the fixture to be flagged "bypasses the gateway" with its kind:
   plugin, local server, or direct entry.
5. Remove one old direct entry. Expect it gone after Apply; undo restores the file bytes exactly.
6. Undo the gateway connection. Expect all three client configs identical to the original.
7. Edit `config.toml` by hand between preview and Apply. Expect Apply to stop with "file changed
   since preview".
8. Open the gateway entry. Expect a link to the gateway's interface and no tool on/off controls.

## Scenario 4 — Plugins (User Story 4)

1. In the sandbox, disable a Claude Code plugin from the page. Expect `claude plugin list --json`
   (sandbox) to show it disabled; undo restores the original settings bytes.
2. Open a Cursor plugin. Expect no on/off control, and a note that Cursor has no plugin on/off
   and where to change it in Cursor (spike S1).
3. Choose "install in Codex" for a Claude plugin. Expect the page to show `codex plugin add …` and
   not run it.

## Scenario 5 — Ask the agent (User Story 5, SC-007)

1. From the page, register the read-only server for Codex. Expect the exact change to be shown and
   applied only after confirmation.
2. Start a Codex session in a known project and ask it to call `show_setup`.
3. Expect the same items and findings as the page's project view; expect no secret values.
4. Ask the agent to disable a plugin through this tool. Expect it to report that the tool cannot
   change settings.

## Automated checks

- `uv run pytest` runs fixture, property and security tests (CI-safe).
- `uv run pytest -m contract` runs local contract tests against the installed real clients with
  sandbox homes; never against real settings.
- A secret-sentinel test fails if any sentinel from fixtures appears in page responses, the change
  log, `scan --json` output or MCP tool output (SC-004).
