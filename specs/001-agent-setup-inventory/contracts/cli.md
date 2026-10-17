# Contract: command line

`<tool>` is a placeholder until the product name is chosen. All commands are local and never send
data off the computer (FR-038).

| Command | Behavior | Exit codes |
| --- | --- | --- |
| `uvx <tool>` or `<tool>` | Starts the local page on `127.0.0.1` (default port 47800, next free port if busy), prints a one-time URL with a token, opens the browser. Read-only until the owner applies a change (FR-007, FR-036) | 0 on normal stop; 2 if no free port |
| `<tool> --no-browser` | Same, without opening the browser | Same |
| `<tool> scan [--json] [--project PATH]` | Prints the redacted inventory, or one project's effective view, then exits. Never writes | 0 ok; 3 if a client file could not be read (output still produced, items marked unknown) |
| `<tool> mcp` | Runs the read-only MCP server over stdio for AI clients (FR-030, FR-031) | 0 on stdin close |
| `<tool> --version` | Prints the tool version and the supported client version ranges | 0 |

Rules:

- No command writes client settings. Writes happen only through the page's "Apply" (FR-015).
- `scan --json` output uses the same redacted model as the page and the MCP server
  ([data-model.md](../data-model.md)); secret values never appear (FR-006).
- Recommended install for MCP registration: `uv tool install <tool>`, which gives a stable absolute
  path (`~/.local/bin/<tool>`) for client configs ([research R9](../research.md#r9-read-only-mcp-server)).
