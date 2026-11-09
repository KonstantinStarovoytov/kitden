# Kitden plugin

For Claude Code and Codex. It adds the Kitden MCP server and two skills.

## What the MCP server gives

The server `kitden`, started as `kitden mcp`, lets an agent read your setup: what each client
loads in a project, where each item comes from, and problems such as duplicates. So "show my
setup" or "why does this load twice" gets a true answer in any agent. Its own tools only read.
It also offers the tools of servers moved into the Kitden gateway. You can add this server to any
client without the plugin.

## What the plugin adds

- One install line for the server, and one line to remove it.
- The skill `setup`: sends a change to the Kitden page, so the agent does not edit your settings
  files, and shows the install line when Kitden is missing.
- The skill `audit` (`/kitden:audit` in Claude Code): the agent compares what loads with the
  project you are in and lists what to turn off. It judges by what the project is; Kitden's
  tools do not tell how often an item is used. You make the changes on the page.

The plugin adds nothing that runs by itself.

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
