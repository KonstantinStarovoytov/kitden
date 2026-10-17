# Contract: write matrix

Which actions the first release performs, how, and how it verifies them. Source of truth for each
item's `actions` list ([data-model.md](../data-model.md)). Details and sources:
[research R4](../research.md#r4-write-mechanisms-for-the-first-release).

Legend: **write** = performed after Apply; **spike** = unavailable until the named spike passes
and is recorded; **show** = the page shows the client's own command only; **read** = shown, never
changed; **gateway** = done in the gateway's own interface, not by this tool.

Gateway first (owner decision, 2026-10-17): MCP tools are managed in the gateway. The tool writes
only the gateway entry, the read-only setup server entry, and removals of old direct entries.

| Action | Claude Code / Desktop Code tab | Codex | Cursor |
| --- | --- | --- | --- |
| Connect gateway (user scope by default) | write: `claude mcp add-json -s user` | write: format-preserving edit of `~/.codex/config.toml` | write: edit `~/.cursor/mcp.json` |
| Gateway tools on/off, add a server to the gateway | gateway | gateway | gateway |
| Remove an old direct MCP entry | write: `claude mcp remove -s <scope>` | write: TOML edit | write: JSON edit |
| Add, turn on or off individual MCP servers in client files | not offered (FR-025) | not offered | not offered |
| MCP bundled in plugins, local MCP servers | read, flagged "bypasses the gateway" | read, flagged | read, flagged |
| MCP from `claude_desktop_config.json` | read, flagged if direct | — | — |
| Plugin on/off | write: `claude plugin enable|disable -s <scope> --json` | write: `plugins."<id>".enabled` for plugins with a `config.toml` entry; remote plugins: read, stored in the account ([spike S4](../spikes/s4-codex-app.md)) | read: Cursor has no on/off; the page says where to change it in Cursor ([spike S1](../spikes/s1-cursor-plugins.md)) |
| Plugin install, update, uninstall | show | show | show |
| Move plugin to another client | show the target client's install command | show | show |
| Marketplace add or remove | show | show | show |
| Skills and hooks | read | read | read |
| Register read-only MCP server | write: `claude mcp add-json -s user` (after confirmation) | write: TOML edit (after confirmation) | write: `~/.cursor/mcp.json` edit (after confirmation) |
| Gateway login (OAuth) | show `/mcp` login steps | show `codex mcp login <name>` | show the client's login step |

Rules for every **write**:

- Follow the safe write pattern ([research R7](../research.md#r7-safe-write-pattern)): preview,
  stale check, backup, atomic write, verify, undo.
- Verify with the client's own listing where it exists (`claude plugin list --json`,
  `codex mcp list --json`, `codex plugin list --json`), redacting its output.
- Undo writes the saved bytes back when the file is unchanged since apply. For `~/.claude.json`,
  which Claude Code rewrites during normal use, only the edited entry is compared before apply
  and undo, and undo restores just that entry if other parts changed.
- Gateway keys are written as references: Claude `${VAR}`, Codex `bearer_token_env_var` /
  `env_http_headers`, Cursor `${env:NAME}` (FR-035).
- Codex uses our own format-preserving edit, not `codex mcp add`, because that command drops
  comments inside `[mcp_servers]` (constitution III: preserve settings; see plan Complexity
  Tracking).
- Mark restart needs: Codex and Cursor after config edits; Claude Code plugins after
  `/reload-plugins` or a new session; Claude MCP changes in `~/.claude.json` in a new session.
- When a spike passes, its result is recorded in `specs/001-agent-setup-inventory/spikes/` and
  this matrix is updated before the capability is enabled.
