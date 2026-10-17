# Contract: read-only MCP server ("show my setup")

Started by AI clients as `<absolute path>/<tool> mcp` over stdio. Built with the official MCP SDK
2.x (spec revision 2026-07-28, serving earlier revisions). No network listener.

## Tools

All tools have annotations `readOnlyHint: true`, `destructiveHint: false`,
`idempotentHint: true`, `openWorldHint: false`. No tool starts processes, contacts MCP servers,
or writes files.

| Tool | Input | Output |
| --- | --- | --- |
| `show_setup` | `project_path` (optional; default: the server's current folder), `client` (optional; default: all clients) | Items that load for that client and project: kind, name, source, scope, enabled state, `via_gateway`; redacted |
| `list_findings` | `project_path` (optional) | Findings: type, severity, explanation with source paths |
| `explain_item` | `name`, `kind` (optional), `project_path` (optional) | Every definition of that name across clients and scopes, which one wins, and why |
| `list_projects` | none | Projects with the clients that know them and whether the folder exists |

## Rules

- Output uses the same redacted model as the page ([data-model.md](../data-model.md)); secret values
  never appear (FR-006, SC-004).
- Requests that ask to change settings cannot be fulfilled: there are no change tools (FR-031).
  Tool descriptions say so, and point to the local page for changes.
- Results for the same project match the page's project view (SC-007).
- Unknown state is returned as `unknown` with a reason, never omitted (FR-005).
