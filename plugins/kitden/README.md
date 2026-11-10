# Kitden plugin

For Claude Code and Codex. It adds the Kitden MCP server and two skills, so an agent can tell you
what your coding tools load and why.

The plugin does not hold the program. It needs [Kitden](https://pypi.org/project/kitden/) 0.7.1
or later on this computer:

```bash
uv tool install --python 3.13 kitden
```

The [Kitden README](https://github.com/KonstantinStarovoytov/kitden#get-started) has the Homebrew
line too. Kitden is open source under Apache-2.0, and its code is in the same repository as this
plugin.

## What the MCP server gives

The plugin starts one local program, `kitden mcp --read-only`, and talks to it over stdio. The
server `kitden` has four tools. Each one only reads.

| Tool | What it answers |
| --- | --- |
| `show_setup` | What each client loads in a project, and where each item comes from. |
| `list_findings` | Problems in the setup, such as an item that loads twice. |
| `explain_item` | One name across the clients: every place it is set, and which one loads. |
| `list_projects` | The projects the clients know on this computer. |

The plugin's server offers no other tools. The Kitden gateway is a separate connection that you
make yourself on the Kitden page.

## What the plugin adds

- One install line for the server, and one line to remove it.
- The skill `show-setup`: sends a change to the Kitden page, so the agent does not edit your
  settings files, and shows the install line when Kitden is missing.
- The skill `audit` (`/kitden:audit` in Claude Code): the agent compares what loads with the
  project you are in and lists what to turn off. It judges by what the project is; Kitden's
  tools do not tell how often an item is used. You make the changes on the page.

The plugin adds nothing that runs by itself: no hooks and no commands.

## Try it

- "What MCP servers and skills do you load in this project?"
- "Why does this skill load twice?"
- "Where does the github MCP server come from?"
- `/kitden:audit`

## What it reads

The tools read the settings files of Claude Code, Codex and Cursor on this computer. To learn
versions and plugins they may run the clients' own commands, such as `claude --version` and
`codex plugin list`. They change nothing and do not go online. Secret values, such as tokens in
a server's settings, are replaced with `[secret]` before an answer leaves the server. There is no
account and no telemetry.

## If something goes wrong

- **The client shows the server as failed.** Kitden is missing or older than 0.7.1. Run
  `kitden --version`. If it fails, use the install line above. If it is older, run
  `uv tool upgrade kitden` or `brew upgrade kitden`. Then restart the client.
- **The server runs but the agent has no kitden tools.** Turn the `kitden` server on in the
  client.
- **Anything else.** Open an issue at https://github.com/KonstantinStarovoytov/kitden/issues.

## Install and remove

| Client | Install | Remove |
| --- | --- | --- |
| Claude Code | `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` | `claude plugin uninstall kitden@kitden` |
| Codex | `codex plugin marketplace add KonstantinStarovoytov/kitden`, then `codex plugin add kitden@kitden` | `codex plugin remove kitden@kitden` |

The Claude Code line needs Claude Code 2.1.275 or later (checked 2026-11-05).

Removing the plugin leaves every other setting as it is.
