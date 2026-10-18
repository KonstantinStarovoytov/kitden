# Kitden plugin

Adds to Claude Code or Codex:

- the skill `setup`: how to answer "what loads here" and when to open the Kitden page;
- the read-only MCP server `kitden`, started as `kitden mcp`. It only reads.

It needs Kitden installed on this computer: see the install line in the
[Kitden README](https://github.com/<owner>/kitden#install). Without it, the client shows the server as failed and the skill
tells the agent to show the install line.

| Client | Install | Remove |
| --- | --- | --- |
| Claude Code | `/plugin install kitden --marketplace <owner>/kitden` | `claude plugin uninstall kitden@kitden` |
| Codex | `codex plugin marketplace add <owner>/kitden`, then `codex plugin add kitden@kitden` | `codex plugin remove kitden@kitden` |

Removing the plugin leaves every other setting as it is.
