# Spike S5: Cursor "Third-Party Imports" switch

Date: 2026-10-17. Cursor 3.21.16. Method: read the installed app code and the names of stored
keys. Nothing was changed.

## Result: passed

| Question | Answer |
| --- | --- |
| Where is the switch stored? | Cursor's reactive storage: the `ItemTable` row `src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl.persistentStorage.applicationUser` in `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` |
| Field name | `thirdPartyExtensibilityEnabled` (label: "Include Third-Party Plugins, Skills, and Other Configs") |
| Default | `true` (code: `thirdPartyExtensibilityEnabled: Ih(!0)`) |
| Related fields | `importPluginsFromClaudeOnBoot` (default `true`), `importClaudeCodeAgents` (default `false`), `claudeMdEnabled` (default `false`) |
| Owner's machine | None of these fields is stored, so all defaults apply: third-party imports are **on** |

Evidence: `out/vs/workbench/workbench.desktop.main.js` reads the field through
`storageService` in the MCP service, the rules provider and the agent host, and refreshes plugin
MCP servers when it changes.

## What the tool does

- Read the four fields from that row, read-only, and use the defaults above when a field is missing.
- When `thirdPartyExtensibilityEnabled` is true, treat Claude Code and Codex skills, hooks and
  plugins as loaded by Cursor (cross-loaded findings, FR-012).
- Never write this row: it is undocumented, app-owned storage (constitution III).
- Label the result "from Cursor's internal state; may change between versions".
