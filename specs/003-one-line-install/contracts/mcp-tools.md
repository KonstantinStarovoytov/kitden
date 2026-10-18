# Contract: read-only MCP server (unchanged)

The [feature 002 MCP contract](../../002-kitden-rename/contracts/mcp-tools.md) stays as it is:
four read-only tools, no process started, no file written, the same redacted model as the page.
This feature adds no tool and changes no output.

What changes is only how clients come to start the server:

| Way | Entry | Who writes it |
| --- | --- | --- |
| The Kitden page, "Let agents read this setup" | `<absolute path>/kitden mcp`, user level | Kitden, after Apply, with backup and Undo (feature 001, FR-032) |
| The plugin (Claude Code, Codex) | `kitden mcp` by name, from the plugin's `.mcp.json` / `mcp.json` | the client, when the user installs the plugin |
| The Cursor link | `kitden mcp` by name, user level | Cursor, after the user confirms |

The page reports a plugin-provided server as `plugin` on the Agents place and never adds a second
entry for that client (FR-014).
