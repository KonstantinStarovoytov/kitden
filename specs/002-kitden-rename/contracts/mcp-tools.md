# Contract: read-only MCP server changes

The [feature 001 MCP contract](../../001-agent-setup-inventory/contracts/mcp-tools.md) stays, with
these changes:

- Server name: `kitden`. Clients start it as `<absolute path>/kitden mcp`.
- Tool descriptions send the developer to the page with `kitden open`.
- `explain_item` returns two more fields per definition: `overridden` and `merged` (feature 001
  final review). With a project, definitions from other projects are left out.
