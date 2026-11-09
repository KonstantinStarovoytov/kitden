# Kitden plugin

Adds to Claude Code or Codex:

- the skill `setup`: how to answer "what loads here" and when to open the Kitden page;
- the MCP server `kitden`, started as `kitden mcp`. Its own tools only read. It also offers the
  tools of servers moved into the Kitden gateway.

It needs Kitden installed on this computer first:

```bash
uv tool install --python 3.13 kitden
```

The [Kitden README](https://github.com/KonstantinStarovoytov/kitden#get-started) has the Homebrew
line too. Without Kitden, the client shows the server as failed and the skill tells the agent to
show this install line.

| Client | Install | Remove |
| --- | --- | --- |
| Claude Code | `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` | `claude plugin uninstall kitden@kitden` |
| Codex | `codex plugin marketplace add KonstantinStarovoytov/kitden`, then `codex plugin add kitden@kitden` | `codex plugin remove kitden@kitden` |

The Claude Code line needs Claude Code 2.1.275 or later (checked 2026-11-05).

Removing the plugin leaves every other setting as it is.
