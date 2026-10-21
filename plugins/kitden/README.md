# Kitden plugin

Adds to Claude Code or Codex:

- the skill `setup`: how to answer "what loads here" and when to open the Kitden page;
- the MCP server `kitden`, started as `kitden mcp`. Its own tools only read. It also offers the
  tools of servers moved into the Kitden gateway.

It needs Kitden installed on this computer: see the install line in the
[Kitden README](https://github.com/KonstantinStarovoytov/kitden#install). Without it, the client shows the server as failed and the skill
tells the agent to show the install line.

| Client | Install | Remove |
| --- | --- | --- |
| Claude Code | `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` | `claude plugin uninstall kitden@kitden` |
| Codex | `codex plugin marketplace add KonstantinStarovoytov/kitden`, then `codex plugin add kitden@kitden` | `codex plugin remove kitden@kitden` |

Removing the plugin leaves every other setting as it is.
